#!/usr/bin/env python3
"""
Convert DICOM neuroimaging data into a BIDS dataset with validation

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
2019-03-22 JMT Add BIDS validation

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

__version__ = '1.2.3'

import os
import sys
import argparse
import subprocess
from glob import glob

import bidskit.io as bio
import bidskit.translate as btr
from bidskit.bidstree import BIDSTree
from bidskit.organize import organize_series


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

    print('\n------------------------------------------------------------')
    print('BIDSKIT %s' % __version__)
    print('------------------------------------------------------------')

    # Check for minimum dcm2niix version (mostly for multirecon suffix handling)
    btr.check_dcm2niix_version('v1.0.20181125')

    # Create a BIDS directory tree object to handle file locations
    # Creates directory
    btree = BIDSTree(dataset_dir, overwrite)

    print('\nSource data directory      : %s' % btree.sourcedata_dir)
    print('Working Directory          : %s' % btree.work_dir)
    print('Use Session Directories    : %s' % ('No' if no_sessions else 'Yes'))
    print('Overwrite Existing Files   : %s' % ('Yes' if overwrite else 'No'))

    # Load protocol translation and exclusion info from derivatives/conversion directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the derivatives/conversion directory.
    # This template should be completed by the user and the conversion rerun.
    translator = btree.read_translator()

    if translator and os.path.isdir(btree.work_dir):

        print('\n------------------------------------------------------------')
        print('Pass 2 : Populating BIDS directory')
        print('------------------------------------------------------------')
        first_pass = False

    else:

        print('\n------------------------------------------------------------')
        print('Pass 1 : DICOM to Nifti conversion and translator creation')
        print('------------------------------------------------------------')
        first_pass = True

    subject_dir_list = []

    # Loop over subject directories in DICOM root
    for dcm_sub_dir in glob(btree.sourcedata_dir + '/*/'):

        sid = os.path.basename(dcm_sub_dir.strip('/'))

        # Check that subject ID is legal
        btr.check_subject_session(sid)

        subject_dir_list.append(dataset_dir + "/sub-" + sid)

        print('\n------------------------------------------------------------')
        print('Processing subject ' + sid)
        print('------------------------------------------------------------')

        # Handle subject vs subject/session directory lists
        if no_sessions:
            dcm_dir_list = [dcm_sub_dir]
        else:
            dcm_dir_list = glob(dcm_sub_dir + '/*/')

        # Loop over source data session directories in subject directory
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

                # Check that session ID is legal
                btr.check_subject_session(ses)

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

            # Organize dcm2niix output into BIDS subject/session directories
            organize_series(work_conv_dir, first_pass, translator, bids_ses_dir, sid, ses,
                           args.clean_conv_dir, overwrite)

    if first_pass:

        # Create a template protocol dictionary
        btree.write_translator(translator)

    if not args.skip_if_pruning:

        print("\nSubject directories to prune:  " + ", ".join(subject_dir_list))

        for bids_subj_dir in subject_dir_list:
            btr.prune_intendedfors(bids_subj_dir, True)

    # Finally validate that all is well with the BIDS dataset
    if not first_pass:
        btree.validate()

    # Clean exit
    sys.exit(0)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
