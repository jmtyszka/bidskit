#!/usr/bin/env python3
"""
Convert flat DICOM file set into a BIDS-compliant Nifti structure

Authors
----
Mike Tyszka, Caltech Brain Imaging Center
Remya Nair, Caltech Brain Imaging Center
Julien Dubois, Caltech and Cedars Sinai Medical Center

Dates
----
2016-08-03 JMT From scratch
2016-11-04 JMT Add session directory to DICOM heirarchy
2017-11-09 JMT Added support for DWI, no sessions, IntendedFor and TaskName
2018-03-09 JMT Fixed IntendedFor handling (#20, #27) and run-number issues (#28)
               Migrated to pydicom v1.0.1 (note namespace change to pydicom)
2019-02-25 JMT Fixed arbitrary run ordering (sorted glob)
2019-03-20 JMT Restructure as PyPI application with BIDS 1.2 compliance

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

__version__ = '1.2'

import os
import sys
import argparse
import subprocess
import shutil
from glob import glob

import bidskit.io as bio
import bidskit.translate as btr
from bidskit.bidstree import BIDSTree


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')

    parser.add_argument('-d', '--dataset', default='.', help='BIDS dataset directory containing sourcedata subdirectory')

    parser.add_argument('--no-sessions', action='store_true', default=False,
                        help='Do not use session sub-directories')

    parser.add_argument('--overwrite', action='store_true', default=False,
                        help='Overwrite existing files')

    parser.add_argument('--skip_if_pruning', action='store_true', default=False,
                        help='Skip pruning of nonexistent IntendedFor items in json files')
    
    parser.add_argument('--clean_conv_dir', action='store_true', default=False,
                        help='Clean up conversion directory')

    # Parse command line arguments
    args = parser.parse_args()
    dataset_dir = os.path.realpath(args.dataset)
    no_sessions = args.no_sessions
    overwrite = args.overwrite

    # Create a BIDS directory tree object to handle file locations
    # Creates directory
    btree = BIDSTree(dataset_dir, overwrite)

    print('')
    print('------------------------------------------------------------')
    print('DICOM to BIDS Converter')
    print('------------------------------------------------------------')
    print('Software Version           : %s' % __version__)
    print('Source data directory      : %s' % btree.sourcedata_dir)
    print('Working Directory          : %s' % btree.work_dir)
    print('Use Session Directories    : %s' % ('No' if no_sessions else 'Yes'))
    print('Overwrite Existing Files   : %s' % ('Yes' if overwrite else 'No'))

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

    subject_dir_list = []

    # Loop over subject directories in DICOM root
    for dcm_sub_dir in glob(btree.sourcedata_dir + '/*/'):

        sid = os.path.basename(dcm_sub_dir.strip('/'))
        subject_dir_list.append(dataset_dir + "/sub-" + sid)

        print('')
        print('------------------------------------------------------------')
        print('Processing subject ' + sid)
        print('------------------------------------------------------------')

        # Handle subj vs subj/session directory lists
        if no_sessions:
            dcm_dir_list = [dcm_sub_dir]
        else:
            dcm_dir_list = glob(dcm_sub_dir + '/*/')

        # Loop over session directories in subject directory
        for dcm_dir in dcm_dir_list:

            # BIDS subject, session and conversion directories
            sub_prefix = 'sub-' + sid

            if no_sessions:
                # If session subdirs aren't being used, *_ses_dir = *sub_dir
                # Use an empty ses_prefix with os.path.join to achieve this
                ses = ''
                ses_prefix = ''
            else:
                ses = os.path.basename(dcm_dir.strip('/'))
                ses_prefix = 'ses-' + ses
                print('  Processing session ' + ses)

            # Working conversion directories
            work_subj_dir = os.path.join(btree.work_dir, sub_prefix)
            work_conv_dir = os.path.join(work_subj_dir, ses_prefix)

            # BIDS source directory directories
            bids_subj_dir = os.path.join(dataset_dir, sub_prefix)
            bids_ses_dir = os.path.join(bids_subj_dir, ses_prefix)

            print('  Working subject directory : %s' % work_subj_dir)
            if not no_sessions:
                print('  Working session directory : %s' % work_conv_dir)
            print('  BIDS subject directory  : %s' % bids_subj_dir)
            if not no_sessions:
                print('  BIDS session directory  : %s' % bids_ses_dir)

            # Safely create working directory for current subject
            # Flag for conversion if no working directory existed
            if not os.path.isdir(work_conv_dir):
                os.makedirs(work_conv_dir)
                needs_converting = True
            else:
                needs_converting = False

            if first_pass or needs_converting:

                # Run dcm2niix conversion into working conversion directory
                print('  Converting all DICOM images in %s' % dcm_dir)
                devnull = open(os.devnull, 'w')
                subprocess.call(['dcm2niix', '-b', 'y', '-z', 'y', '-f', '%n--%d--%q--%s',
                                 '-o', work_conv_dir, dcm_dir],
                                stdout=devnull, stderr=subprocess.STDOUT)

            if not first_pass:

                # Get subject age and sex from representative DICOM header
                dcm_info = bio.dcm_info(dcm_dir)

                # Add line to participants TSV file
                btr.add_participant_record(dataset_dir, sid, dcm_info['Age'], dcm_info['Sex'])

            # Run dcm2niix output to BIDS source conversions
            run_conversion(work_conv_dir, first_pass, translator, bids_ses_dir, sid, ses,
                           args.clean_conv_dir, overwrite)

    if first_pass:
        # Create a template protocol dictionary
        btree.write_translator(translator)

    if not args.skip_if_pruning:
        print("Subject directories to prune:  " + ", ".join(subject_dir_list))
        for bids_subj_dir in subject_dir_list:
            btr.prune_intendedfors(bids_subj_dir, True)

    # Clean exit
    sys.exit(0)


def run_conversion(conv_dir, first_pass, prot_dict, src_dir, sid, ses, clean_conv_dir, overwrite=False):
    """
    Run dcm2niix output to BIDS source conversions

    :param conv_dir: string
        Working conversion directory
    :param first_pass: boolean
        Flag for first pass conversion
    :param prot_dict: dictionary
        Protocol translation dictionary
    :param src_dir: string
        BIDS source output subj or subj/session directory
    :param sid: string
        subject ID
    :param ses: string
        session name or number
    :param clean_conv_dir: bool
        clean up conversion directory
    :param overwrite: bool
        overwrite flag
    :return:
    """

    # Flag for working conversion directory cleanup
    do_cleanup = clean_conv_dir

    # Proceed if conversion directory exists
    if os.path.isdir(conv_dir):

        # Get Nifti file list ordered by acquisition time
        nii_list, json_list = btr.ordered_file_list(conv_dir)
        
        # Infer run numbers accounting for duplicates.
        # Only used if run-* not present in translator BIDS filename stub
        run_no = btr.auto_run_no(nii_list)

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        for fc, src_nii_fname in enumerate(nii_list):

            # Parse image filename into fields
            info = bio.parse_dcm2niix_fname(src_nii_fname)

            # Check if we're creating new protocol dictionary
            if first_pass:

                print('  Adding protocol %s to dictionary template' % info['SerDesc'])

                # Add current protocol to protocol dictionary
                # Use default EXCLUDE_* values which can be changed (or not) by the user
                prot_dict[info['SerDesc']] = ["EXCLUDE_BIDS_Directory", "EXCLUDE_BIDS_Name", "UNASSIGNED"]

            else:

                # JSON sidecar for this image
                src_json_fname = json_list[fc]

                # Warn if not found and continue
                if not os.path.isfile(src_json_fname):
                    print('* WARNING: JSON sidecar %s not found' % src_json_fname)
                    continue

                if info['SerDesc'] in prot_dict.keys():

                    if prot_dict[info['SerDesc']][0].startswith('EXCLUDE'):

                        # Skip excluded protocols
                        print('* Excluding protocol ' + str(info['SerDesc']))

                    else:

                        print('  Organizing ' + str(info['SerDesc']))

                        # Use protocol dictionary to determine purpose folder, BIDS filename suffix and fmap linking
                        bids_purpose, bids_suffix, bids_intendedfor = prot_dict[info['SerDesc']]

                        # Safely add run-* key to BIDS suffix
                        bids_suffix = btr.add_run_number(bids_suffix, run_no[fc])

                        # Assume the IntendedFor field should aslo have a run- added
                        prot_dict = btr.add_intended_run(prot_dict, info, run_no[fc])

                        # Create BIDS purpose directory
                        bids_purpose_dir = os.path.join(src_dir, bids_purpose)
                        bio.safe_mkdir(bids_purpose_dir)

                        # Complete BIDS filenames for image and sidecar
                        if ses:
                            bids_prefix = 'sub-' + sid + '_ses-' + ses + '_'
                        else:
                            bids_prefix = 'sub-' + sid + '_'

                        # Construct BIDS source Nifti and JSON filenames
                        bids_nii_fname = os.path.join(bids_purpose_dir, bids_prefix + bids_suffix + '.nii.gz')
                        bids_json_fname = bids_nii_fname.replace('.nii.gz', '.json')

                        # Add prefix and suffix to IntendedFor values
                        if 'UNASSIGNED' not in bids_intendedfor:
                            if isinstance(bids_intendedfor, str):
                                # Single linked image
                                bids_intendedfor = btr.build_intendedfor(sid, ses, bids_intendedfor)
                            else:
                                # Loop over all linked images
                                for ifc, ifstr in enumerate(bids_intendedfor):
                                    # Avoid multiple substitutions
                                    if '.nii.gz' not in ifstr:
                                        bids_intendedfor[ifc] = btr.build_intendedfor(sid, ses, ifstr)

                        # Special handling for specific purposes (anat, func, fmap, etc)
                        # This function populates BIDS structure with the image and adjusted sidecar
                        btr.purpose_handling(bids_purpose, bids_intendedfor, info['SeqName'],
                                             src_nii_fname, src_json_fname,
                                             bids_nii_fname, bids_json_fname,
                                             overwrite)
                else:
                    # Skip protocols not in the dictionary
                    print('* Protocol ' + str(info['SerDesc']) + ' is not in the dictionary, did not convert.')

        if not first_pass:

            # Optional working directory cleanup after Pass 2
            if do_cleanup:
                print('  Cleaning up temporary files')
                shutil.rmtree(conv_dir)
            else:
                print('  Preserving conversion directory')


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
