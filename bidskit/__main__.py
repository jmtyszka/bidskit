#!/usr/bin/env python
"""
Convert DICOM neuroimaging data into a BIDS dataset with validation

Authors
----
Mike Tyszka, Caltech Brain Imaging Center
Remya Nair, Caltech Brain Imaging Center
Julien Dubois, Caltech and Cedars Sinai Medical Center

MIT License

Copyright (c) 2017-2019 Mike Tyszka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import sys
import argparse
import subprocess
import pkg_resources
from glob import glob

from . import io as bio
from . import translate as btr
from . import dcm2niix as d2n
from . import fmaps
from .bidstree import BIDSTree


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')

    parser.add_argument('-d', '--dataset', default='.',
                        help='BIDS dataset directory containing sourcedata subdirectory')

    parser.add_argument('-s', '--subjects', nargs='+', default=[],
                        help='List of subject IDs to convert (eg --subjects alpha bravo charlie)')

    parser.add_argument('--no-sessions', action='store_true', default=False,
                        help='Do not use session sub-directories')

    parser.add_argument('--no-anon', action='store_true', default=False,
                        help='Do not anonymize BIDS output (eg for phantom data)')

    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite existing files')

    parser.add_argument('--skip-if-pruning', action='store_true', default=False,
                        help='Skip pruning of nonexistent IntendedFor items in json files')
    
    parser.add_argument('--clean-conv-dir', action='store_true', default=False,
                        help='Clean up conversion directory')

    parser.add_argument('--bind-fmaps', action='store_true', default=False,
                        help='Bind fieldmaps to fMRI series using IntendedFor field')

    parser.add_argument('--compression', required=False, default='o',
                        help='gzip compression flag for dcm2niix (y, o, i, n, 3 depending on dcm2niix version) [o]')

    parser.add_argument('--recon', action='store_true', default=False,
                        help='Add recon- key to output filenames for bias- and distortion-corrected images')

    parser.add_argument('--complex', action='store_true', default=False,
                        help='Add part- key to output filenames for complex-valued images')

    parser.add_argument('--multiecho', action='store_true', default=False,
                        help='Add echo- key to output filenames')

    parser.add_argument('--auto', action='store_true', default=False,
                        help='Automatically generate protocol translator from series descriptions and sequence parameters')

    parser.add_argument('-V', '--version', action='store_true', default=False,
                        help='Display bidskit version number and exit')

    # Parse command line arguments
    args = parser.parse_args()
    dataset_dir = os.path.realpath(args.dataset)
    subject_list = args.subjects
    no_sessions = args.no_sessions
    no_anon = args.no_anon
    overwrite = args.overwrite
    bind_fmaps = args.bind_fmaps
    gzip_type = args.compression
    auto = args.auto

    # Set Nifti image extension from gzip type
    nii_ext = ".nii" if 'n' in gzip_type else ".nii.gz"

    # Filename key flag dict - pass to organize
    key_flags = {
        'Part': args.complex,
        'Echo': args.multiecho,
        'Recon': args.recon
    }

    # Read version from setup.py
    ver = pkg_resources.get_distribution('bidskit').version

    if args.version:
        print('BIDSKIT {}'.format(ver))
        sys.exit(1)

    print('')
    print('------------------------------------------------------------')
    print('BIDSKIT {}'.format(ver))
    print('------------------------------------------------------------')

    if not os.path.isdir(os.path.join(dataset_dir, 'sourcedata')):
        print('* sourcedata folder not found in {}'.format(dataset_dir))
        print('* bidskit expects this folder to exist and contain DICOM series')
        print('* Please see the bidskit documentation at')
        print('* https://github.com/jmtyszka/bidskit/blob/master/docs/QuickStart.md')
        sys.exit(1)

    # Check for minimum dcm2niix version (mostly for multirecon suffix handling)
    d2n.check_dcm2niix_version('v1.0.20181125')

    # Create a BIDS directory tree object to handle file locations
    # Creates directory
    btree = BIDSTree(dataset_dir, overwrite)

    if len(subject_list) > 1:
        subj_to_convert = ' '.join(subject_list)
    else:
        subj_to_convert = 'All'

    print('')
    print(f"Subjects to convert        : {subj_to_convert}")
    print(f"Source data directory      : {btree.sourcedata_dir}")
    print(f"Working Directory          : {btree.work_dir}")
    print(f"Use Session Directories    : {'No' if no_sessions else 'Yes'}")
    print(f"Overwrite Existing Files   : {'Yes' if overwrite else 'No'}")
    print(f"Anonymize BIDS Output      : {'No' if no_anon else 'Yes'}")
    print(f"Auto translate             : {'Yes' if auto else 'No'}")
    print(f"Bind fieldmaps             : {'Yes' if bind_fmaps else 'No'}")
    print(f"GZIP compression           : {gzip_type.upper()}")
    print(f"Recon filename key         : {key_flags['Recon']}")
    print(f"Part filename key          : {key_flags['Part']}")
    print(f"Echo filename key          : {key_flags['Echo']}")

    # Load protocol translation and exclusion info from derivatives/conversion directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the derivatives/conversion directory.
    # This template should be completed by the user and the conversion rerun.
    translator = btree.read_translator()

    if translator and os.path.isdir(btree.work_dir):

        print('')
        print('------------------------------------------------------------')
        print('Pass 2 : Populating BIDS directory')
        print('------------------------------------------------------------')
        first_pass = False

    else:

        print('')
        print('------------------------------------------------------------')
        print('Pass 1 : DICOM to Nifti conversion and translator creation')
        print('------------------------------------------------------------')
        first_pass = True

    # Init list of output subject directories
    out_subj_dir_list = []

    # Init list of source subject directories from sourcedata contents if no subjects provided in command line
    if len(subject_list) < 1:
        print('  Creating subject list from sourcedata contents')
        subject_list = []
        for it in os.scandir(btree.sourcedata_dir):
            if it.is_dir():
                subject_list.append(it.name)
        print('  Found {:d} subjects in sourcedata folder'.format(len(subject_list)))

    # Loop over subject list (either from sourcedata contents or command line)
    for sid in subject_list:

        print('')
        print('------------------------------------------------------------')
        print('Processing subject {}'.format(sid))
        print('------------------------------------------------------------')

        # Full path to subject directory in sourcedata/
        src_subj_dir = os.path.realpath(os.path.join(btree.sourcedata_dir, sid))

        # BIDS subject ID with prefix
        subj_prefix = 'sub-{:s}'.format(sid)

        # Add full path to subject output directory to running list
        out_subj_dir_list.append(os.path.join(dataset_dir, subj_prefix))

        # Create list of DICOM directories to convert
        # This will be either a session or series folder list depending on no-sessions command line flag
        if no_sessions:
            dcm_dir_list = [src_subj_dir]
        else:
            dcm_dir_list = sorted(glob(os.path.join(src_subj_dir, '*')))

        # Loop over DICOM directories in subject directory
        for dcm_dir in dcm_dir_list:

            if no_sessions:

                # If session subdirs aren't being used, *_ses_dir = *sub_dir
                # Use an empty ses_prefix with os.path.join to achieve this
                ses = ''
                ses_prefix = ''

            else:

                ses = os.path.basename(os.path.normpath(dcm_dir))

                ses_prefix = 'ses-{:s}'.format(ses)
                print('  Processing session ' + ses)

            # Working conversion directories
            work_subj_dir = os.path.join(btree.work_dir, subj_prefix)
            work_conv_dir = os.path.join(work_subj_dir, ses_prefix)

            # BIDS source directory directories
            bids_subj_dir = os.path.join(dataset_dir, subj_prefix)
            bids_ses_dir = os.path.join(bids_subj_dir, ses_prefix)

            print('  Working subject directory : %s' % work_subj_dir)
            if not no_sessions:
                print('  Working session directory : %s' % work_conv_dir)
            print('  BIDS subject directory  : %s' % bids_subj_dir)
            if not no_sessions:
                print('  BIDS session directory  : %s' % bids_ses_dir)

            # Safely create working directory for current subject
            # Flag for conversion if no working directory exists
            if not os.path.isdir(work_conv_dir):
                os.makedirs(work_conv_dir)
                needs_converting = True
            else:
                needs_converting = False

            if first_pass or needs_converting:

                # Run dcm2niix conversion into working conversion directory
                print('  Converting all DICOM images in %s' % dcm_dir)

                # BIDS anonymization flag - default 'y'
                anon = 'n' if no_anon else 'y'

                # Compose command
                cmd = ['dcm2niix',
                       '-b', 'y',
                       '-ba', anon,
                       '-z', gzip_type,
                       '-f', '%n--%d--%q--%s',
                       '-o', work_conv_dir,
                       dcm_dir]

                with open(os.devnull, 'w') as devnull:
                    subprocess.run(cmd, stdout=devnull, stderr=devnull)

            if not first_pass:

                # Get subject age and sex from representative DICOM header
                dcm_info = bio.dcm_info(dcm_dir)

                # Add line to participants TSV file
                btr.add_participant_record(dataset_dir, sid, dcm_info['Age'], dcm_info['Sex'])

            # Organize dcm2niix output into BIDS subject/session directories
            d2n.organize_series(
                work_conv_dir,
                first_pass,
                translator,
                bids_ses_dir,
                sid,
                ses,
                key_flags,
                nii_ext,
                args.clean_conv_dir,
                overwrite,
                auto
            )

    if first_pass:

        # Write a template or auto built translator dictionary to code/Protocol_Translator.json
        btree.write_translator(translator)

    if not args.skip_if_pruning:

        print('')
        print('Subject directories to prune:  ' + ', '.join(out_subj_dir_list))

        for bids_subj_dir in out_subj_dir_list:
            fmaps.prune_intendedfors(bids_subj_dir, True)

    if not first_pass:

        if args.bind_fmaps:

            print('')
            print('Binding nearest fieldmap to each functional series')
            for bids_subj_dir in out_subj_dir_list:
                fmaps.bind_fmaps(bids_subj_dir, no_sessions)

    # Finally validate that all is well with the BIDS dataset
    if not first_pass:
        btree.validate()

    # Clean exit
    sys.exit(0)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
