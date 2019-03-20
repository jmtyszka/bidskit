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


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')

    parser.add_argument('-i', '--indir', default='dicom',
                        help='DICOM input directory with Subject/Session/Image organization [dicom]')

    parser.add_argument('-o', '--outdir', default='source',
                        help='Output BIDS source directory [source]')

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
    dcm_root_dir = os.path.realpath(args.indir)
    no_sessions = args.no_sessions
    overwrite = args.overwrite

    # Place derivatives and working directories in parent of BIDS source directory
    bids_src_dir = os.path.realpath(args.outdir)
    bids_root_dir = os.path.dirname(bids_src_dir)
    bids_deriv_dir = os.path.join(bids_root_dir, 'derivatives', 'conversion')
    work_dir = os.path.join(bids_root_dir, 'work', 'conversion')

    # Safely create the BIDS working, source and derivatives directories
    bio.safe_mkdir(work_dir)
    bio.safe_mkdir(bids_src_dir)
    bio.safe_mkdir(bids_deriv_dir)

    print('')
    print('------------------------------------------------------------')
    print('DICOM to BIDS Converter')
    print('------------------------------------------------------------')
    print('Software Version           : %s' % __version__)
    print('DICOM Root Directory       : %s' % dcm_root_dir)
    print('BIDS Source Directory      : %s' % bids_src_dir)
    print('BIDS Derivatives Directory : %s' % bids_deriv_dir)
    print('Working Directory          : %s' % work_dir)
    print('Use Session Directories    : %s' % ('No' if no_sessions else 'Yes'))
    print('Overwrite Existing Files   : %s' % ('Yes' if overwrite else 'No'))

    # Load protocol translation and exclusion info from derivatives/conversion directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the derivatives/conversion directory.
    # This template should be completed by the user and the conversion rerun.
    prot_dict_json = os.path.join(bids_deriv_dir, 'Protocol_Translator.json')
    prot_dict = bio.load_prot_dict(prot_dict_json)

    if prot_dict and os.path.isdir(work_dir):
        print('')
        print('------------------------------------------------------------')
        print('Pass 2 : Populating BIDS source directory')
        print('------------------------------------------------------------')
        first_pass = False
    else:
        print('')
        print('------------------------------------------------------------')
        print('Pass 1 : DICOM to Nifti conversion and dictionary creation')
        print('------------------------------------------------------------')
        first_pass = True

    # Initialize BIDS source directory contents
    if not first_pass:
        bio.init(bids_src_dir, overwrite)

    subject_dir_list = []

    # Loop over subject directories in DICOM root
    for dcm_sub_dir in glob(dcm_root_dir + '/*/'):

        sid = os.path.basename(dcm_sub_dir.strip('/'))
        subject_dir_list.append(bids_src_dir + "/sub-" + sid)

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
            work_subj_dir = os.path.join(work_dir, sub_prefix)
            work_conv_dir = os.path.join(work_subj_dir, ses_prefix)

            # BIDS source directory directories
            bids_src_subj_dir = os.path.join(bids_src_dir, sub_prefix)
            bids_src_ses_dir = os.path.join(bids_src_subj_dir, ses_prefix)

            print('  BIDS working subject directory : %s' % work_subj_dir)
            if not no_sessions:
                print('  BIDS working session directory : %s' % work_conv_dir)
            print('  BIDS source subject directory  : %s' % bids_src_subj_dir)
            if not no_sessions:
                print('  BIDS source session directory  : %s' % bids_src_ses_dir)

            # Safely create BIDS working directory
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
                btr.add_participant_record(bids_src_dir, sid, dcm_info['Age'], dcm_info['Sex'])

            # Run dcm2niix output to BIDS source conversions
            run_conversion(work_conv_dir, first_pass, prot_dict, bids_src_ses_dir, sid, ses,
                           args.clean_conv_dir, overwrite)

    if first_pass:
        # Create a template protocol dictionary
        bio.create_prot_dict(prot_dict_json, prot_dict)

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

        # glob returns the full relative path from the tmp dir
        # Note that glob returns arbitrarily ordered filenames, which must be sorted according to serNo
        # for the run ordering below to work correctly.
        filelisttmp = glob(os.path.join(conv_dir, '*.nii*'))
        sernolist = [int(bio.parse_dcm2niix_fname(file)['SerNo']) for file in filelisttmp]
        filelist = [file for _, file in sorted(zip(sernolist, filelisttmp))]
        
        # Infer run numbers accounting for duplicates.
        # Only used if run-* not present in translator BIDS filename stub
        run_no = btr.auto_run_no(filelist)

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        for fc, src_nii_fname in enumerate(filelist):

            # Parse image filename into fields
            info = bio.parse_dcm2niix_fname(src_nii_fname)

            # Check if we're creating new protocol dictionary
            if first_pass:

                print('  Adding protocol %s to dictionary template' % info['SerDesc'])

                # Add current protocol to protocol dictionary
                # Use default EXCLUDE_* values which can be changed (or not) by the user
                prot_dict[info['SerDesc']] = ["EXCLUDE_BIDS_Directory", "EXCLUDE_BIDS_Name", "UNASSIGNED"]

            else:

                # Replace Nifti extension ('.nii.gz' or '.nii') with '.json'
                if '.nii.gz' in src_nii_fname:
                    src_json_fname = src_nii_fname.replace('.nii.gz', '.json')
                elif 'nii' in src_nii_fname:
                    src_json_fname = src_nii_fname.replace('.nii', '.json')
                else:
                    print('* Unknown extension: %s' % src_nii_fname)
                    break

                # JSON sidecar for this image
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
