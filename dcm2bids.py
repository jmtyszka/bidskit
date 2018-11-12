#!/usr/bin/env python3
"""
Convert flat DICOM file set into a BIDS-compliant Nifti structure

The DICOM input directory can be organized with or without session subdirectories:

With Session Subdirectories:

<DICOM Directory>/
    <SID 1>/
        <Session 1>/
            Session 1 DICOM files ...
        <Session 2>/
            Session 2 DICOM files ...
        ...
    <SID 2>/
        <Session 1>/
            ...
Here, session refers to all scans performed during a given visit.
Typically this can be given a date-string directory name (eg 20161104 etc).

Without Session Subdirectories:

<DICOM Directory>/
    <SID 1>/
        DICOM files ...
    <SID 2>/
        ...

Usage
----
dcm2bids.py -i <DICOM Directory>[dicom] -o <BIDS Source Directory>[source] [--no-sessions] [--overwrite]

Examples
----
% dcm2bids.py
% dcm2bids.py --no-sessions
% dcm2bids.py -i mydicom -o mybids --no-sessions

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2016-08-03 JMT From scratch
2016-11-04 JMT Add session directory to DICOM heirarchy
2017-11-09 JMT Added support for DWI, no sessions, IntendedFor and TaskName
2018-03-09 JMT Fixed IntendedFor handling (#20, #27) and run-number issues (#28)
               Migrated to pydicom v1.0.1 (note namespace change to pydicom)

MIT License

Copyright (c) 2017-2018 Mike Tyszka

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

__version__ = '1.1.2'

import os
import sys
import argparse
import subprocess
import shutil
import json
import pydicom
import numpy as np
from glob import glob


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
    safe_mkdir(work_dir)
    safe_mkdir(bids_src_dir)
    safe_mkdir(bids_deriv_dir)

    print('')
    print('------------------------------------------------------------')
    print('DICOM to BIDS Converter')
    print('------------------------------------------------------------')
    print('Software Version           : %s' % __version__)
    print('DICOM Root Directory       : %s' % dcm_root_dir)
    print('BIDS Source Directory      : %s' % bids_src_dir)
    print('BIDS Derivatives Directory : %s' % bids_deriv_dir)
    print('Working Directory          : %s' % work_dir)
    print('Use Session Directories    : %s' % ('No' if no_sessions else 'Yes') )
    print('Overwrite Existing Files   : %s' % ('Yes' if overwrite else 'No') )

    # Load protocol translation and exclusion info from derivatives/conversion directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the derivatives/conversion directory.
    # This template should be completed by the user and the conversion rerun.
    prot_dict_json = os.path.join(bids_deriv_dir, 'Protocol_Translator.json')
    prot_dict = bids_load_prot_dict(prot_dict_json)

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
        bids_init(bids_src_dir, overwrite)

    subject_dir_list = []

    # Loop over subject directories in DICOM root
    for dcm_sub_dir in glob(dcm_root_dir + '/*/'):


        SID = os.path.basename(dcm_sub_dir.strip('/'))
        subject_dir_list.append( bids_src_dir + "/sub-" + SID )

        print('')
        print('------------------------------------------------------------')
        print('Processing subject ' + SID)
        print('------------------------------------------------------------')

        # Handle subj vs subj/session directory lists
        if no_sessions:
            dcm_dir_list = [dcm_sub_dir]
        else:
            dcm_dir_list = glob(dcm_sub_dir + '/*/')

        # Loop over session directories in subject directory
        for dcm_dir in dcm_dir_list:

            # BIDS subject, session and conversion directories
            sub_prefix = 'sub-' + SID

            if no_sessions:
                # If session subdirs aren't being used, *_ses_dir = *sub_dir
                # Use an empty ses_prefix with os.path.join to achieve this
                SES = ''
                ses_prefix = ''
            else:
                SES = os.path.basename(dcm_dir.strip('/'))
                ses_prefix = 'ses-' + SES
                print('  Processing session ' + SES)

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
                dcm_info = bids_dcm_info(dcm_dir)

                # Add line to participants TSV file
                #participants_fd.write("sub-%s\t%s\t%s\n" % (SID, dcm_info['Sex'], dcm_info['Age']))
                add_participant_record(bids_src_dir, SID, dcm_info['Age'], dcm_info['Sex'])

            # Run dcm2niix output to BIDS source conversions
            bids_run_conversion(work_conv_dir, first_pass, prot_dict, bids_src_ses_dir, SID, SES, args.clean_conv_dir, overwrite)

    if first_pass:
        # Create a template protocol dictionary
        bids_create_prot_dict(prot_dict_json, prot_dict)


    if not args.skip_if_pruning:
        print( "Subject directories to prune:  " + ", ".join(subject_dir_list) )
        for bids_subj_dir in subject_dir_list:
            bids_prune_intendedfors(bids_subj_dir, True)

    # Clean exit
    sys.exit(0)


def bids_prune_intendedfors(bids_subj_dir, fmap_only):
    """
    Prune out all "IntendedFor" entries pointing to nonexistent files from all json files in given directory tree
    
    :param bids_subj_dir: string
        Subject directory
    :param fmap_only: boolean
        Only looks at json files in an fmap directory
    """
    
    # Traverse through all directories in bids_subj_dir
    for root, dirs, files in os.walk(bids_subj_dir):
        for name in files:
         
            # Only examine json files, ignore dataset_description, and only work in fmap directories if so specified
            if os.path.splitext(name)[1] == ".json" and not name == "dataset_description.json" and (not fmap_only or os.path.basename(root) == "fmap"):
                with open(os.path.join(root, name), 'r+') as f:

                    # Read json file
                    data = json.load(f)
                    
                    if 'IntendedFor' in data:
                     
                        # Prune list of files that do not exist
                        bids_intendedfor = []
                        for i in data['IntendedFor']:
                            i_fullpath = os.path.join(bids_subj_dir, i)
                            if os.path.isfile(i_fullpath):
                                bids_intendedfor.append(i)
                          
                        # Modify IntendedFor with pruned list 
                        data['IntendedFor'] = bids_intendedfor
                        
                        # Update json file
                        f.seek(0)
                        json.dump(data, f, indent=4)
                        f.truncate()
     

def bids_run_conversion(conv_dir, first_pass, prot_dict, src_dir, SID, SES, clean_conv_dir, overwrite=False):
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
    :param SID: string
        subject ID
    :param SES: string
        session name or number
    :param clean_conv_dir: bool
        clean up conversion directory
    :param overwrite: bool
        overwrite flag
    :return:
    """

    # Flag for working conversion directory cleanup
    do_cleanup = clean_conv_dir
    print(prot_dict)
    if os.path.isdir(conv_dir):

        # glob returns the full relative path from the tmp dir
        filelist = glob(os.path.join(conv_dir, '*.nii*'))

        # Infer run numbers accounting for duplicates.
        # Only used if run-* not present in translator BIDS filename stub
        run_no = bids_auto_run_no(filelist)

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        for fc, src_nii_fname in enumerate(filelist):

            # Parse image filename into fields
            info = parse_dcm2niix_fname(src_nii_fname)

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

                # JSON sidecar for this image
                if not os.path.isfile(src_json_fname):
                    print('* JSON sidecar not found : %s' % src_json_fname)
                    break

                if info['SerDesc'] in prot_dict.keys():

                    if prot_dict[info['SerDesc']][0].startswith('EXCLUDE'):

                        # Skip excluded protocols
                        print('* Excluding protocol ' + str(info['SerDesc']))

                    else:

                        print('  Organizing ' + str(info['SerDesc']))

                        # Use protocol dictionary to determine purpose folder, BIDS filename suffix and fmap linking
                        bids_purpose, bids_suffix, bids_intendedfor = prot_dict[info['SerDesc']]

                        # Safely add run-* key to BIDS suffix
                        bids_suffix = bids_add_run_number(bids_suffix, run_no[fc])

                        # Assume the IntendedFor field should aslo have a run- added
                        prot_dict = bids_add_intended_run(prot_dict, info, run_no[fc])

                        # Create BIDS purpose directory
                        bids_purpose_dir = os.path.join(src_dir, bids_purpose)
                        safe_mkdir(bids_purpose_dir)

                        # Complete BIDS filenames for image and sidecar
                        if SES:
                            bids_prefix = 'sub-' + SID + '_ses-' + SES + '_'
                        else:
                            bids_prefix = 'sub-' + SID + '_'

                        # Construct BIDS source Nifti and JSON filenames
                        bids_nii_fname = os.path.join(bids_purpose_dir, bids_prefix + bids_suffix + '.nii.gz')
                        bids_json_fname = bids_nii_fname.replace('.nii.gz','.json')

                        # Add prefix and suffix to IntendedFor values
                        if not 'UNASSIGNED' in bids_intendedfor:
                            if isinstance(bids_intendedfor, str):
                                # Single linked image
                                bids_intendedfor = bids_build_intendedfor(SID, SES, bids_intendedfor)
                            else:
                                # Loop over all linked images
                                for ifc, ifstr in enumerate(bids_intendedfor):
                                    # Avoid multiple substitutions
                                    if not '.nii.gz' in ifstr:
                                        bids_intendedfor[ifc] = bids_build_intendedfor(SID, SES, ifstr)

                        # Special handling for specific purposes (anat, func, fmap, etc)
                        # This function populates BIDS structure with the image and adjusted sidecar
                        bids_purpose_handling(bids_purpose, bids_intendedfor, info['SeqName'],
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


def bids_purpose_handling(bids_purpose, bids_intendedfor, seq_name,
                          work_nii_fname, work_json_fname, bids_nii_fname, bids_json_fname,
                          overwrite=False):
    """
    Special handling for each image purpose (func, anat, fmap, dwi, etc)

    :param bids_purpose: str
    :param bids_intendedfor: str
    :param seq_name: str
    :param work_nii_fname: str
    :param work_json_fname: str
    :param bids_nii_fname: str
    :param bids_json_fname: str
    :param overwrite: bool
    :return:
    """

    # Init DWI sidecars
    work_bval_fname = []
    work_bvec_fname = []
    bids_bval_fname = []
    bids_bvec_fname = []

    # Load the JSON sidecar
    info = bids_read_json(work_json_fname)

    if bids_purpose == 'func':

        if seq_name == 'EP':

            print('    EPI detected')
            bids_events_template(bids_nii_fname, overwrite)

            # Add taskname to BIDS JSON sidecar
            bids_keys = parse_bids_fname(bids_nii_fname)
            if 'task' in bids_keys:
                info['TaskName'] = bids_keys['task']
            else:
                info['TaskName'] = 'unknown'

    elif bids_purpose == 'fmap':

        # Add IntendedFor field if requested through protocol translator
        if not 'UNASSIGNED' in bids_intendedfor:
            info['IntendedFor'] = bids_intendedfor

        # Check for MEGE vs SE-EPI fieldmap images
        # MEGE will have a 'GR' sequence, SE-EPI will have 'EP'

        print('    Identifying fieldmap image type')
        if seq_name == 'GR':

            print('    GRE detected')
            print('    Identifying magnitude and phase images')

            # For Siemens dual gradient echo fieldmaps, three Nifti/JSON pairs are generated from two series
            # Requires dcm2nixx v1.0.20180404 or later for echo number suffix
            # *--GR--<serno>_e1.<ext> : magnitude image from echo 1 (EchoNumber unset, ImageType[2] = "M")
            # *--GR--<serno>_e2.<ext> : magnitude image from echo 2 (EchoNumber = 2, ImageType[2] = "M")
            # *--GR--<serno+1>_e2_ph.<ext> : inter-echo phase difference (EchoNumber = 2, ImageType[2] = "P")

            if 'EchoNumber' in info:

                if info['EchoNumber'] == 2:

                    if 'P' in info['ImageType'][2]:

                        print('    Interecho phase difference detected')

                        # Read phase meta data
                        bids_nii_fname = bids_nii_fname.replace('.nii.gz', '_phasediff.nii.gz')
                        bids_json_fname = bids_json_fname.replace('.json', '_phasediff.json')

                        # Extract TE1 and TE2 from mag and phase JSON sidecars
                        TE1, TE2 = bids_fmap_echotimes(work_json_fname)
                        info['EchoTime1'] = TE1
                        info['EchoTime2'] = TE2

                    else:

                        # Echo 2 magnitude - discard
                        print('    Echo 2 magnitude detected - discarding')
                        bids_nii_fname = []  # Discard image
                        bids_json_fname = []  # Discard sidecar

            else:

                print('    Echo 1 magnitude detected')
                bids_nii_fname = bids_nii_fname.replace('.nii.gz', '_magnitude.nii.gz')
                bids_json_fname = []  # Discard sidecar only

        elif seq_name == 'EP':

            print('    EPI detected')

        else:

            print('    Unrecognized fieldmap detected')
            print('    Simply copying image and sidecar to fmap directory')

    elif bids_purpose == 'anat':

        if seq_name == 'GR_IR':

            print('    IR-prepared GRE detected - likely T1w MP-RAGE or equivalent')

        elif seq_name == 'SE':

            print('    Spin echo detected - likely T1w or T2w anatomic image')

        elif seq_name == 'GR':

            print('    Gradient echo detected')

    elif bids_purpose == 'dwi':

        # Fill DWI bval and bvec working and source filenames
        # Non-empty filenames trigger the copy below
        work_bval_fname = str(work_json_fname.replace('.json', '.bval'))
        bids_bval_fname = str(bids_json_fname.replace('dwi.json', 'dwi.bval'))
        work_bvec_fname = str(work_json_fname.replace('.json', '.bvec'))
        bids_bvec_fname = str(bids_json_fname.replace('dwi.json', 'dwi.bvec'))

    # Populate BIDS source directory with Nifti images, JSON and DWI sidecars
    print('  Populating BIDS source directory')

    if bids_nii_fname:
        safe_copy(work_nii_fname, str(bids_nii_fname), overwrite)

    if bids_json_fname:
        bids_write_json(bids_json_fname, info, overwrite)

    if bids_bval_fname:
        safe_copy(work_bval_fname, bids_bval_fname, overwrite)

    if bids_bvec_fname:
        safe_copy(work_bvec_fname, bids_bvec_fname, overwrite)


def bids_init(bids_src_dir, overwrite=False):
    """
    Initialize BIDS source directory

    :param bids_src_dir: string
        BIDS source directory
    :param overwrite: string
        Overwrite flag
    :return True
    """

    # Create template JSON dataset description
    datadesc_json = os.path.join(bids_src_dir, 'dataset_description.json')
    meta_dict = dict({'BIDSVersion': "1.0.0",
               'License': "This data is made available under the Creative Commons BY-SA 4.0 International License.",
               'Name': "The dataset name goes here",
               'ReferencesAndLinks': "References and links for this dataset go here"})

    # Write JSON file
    bids_write_json(datadesc_json, meta_dict, overwrite)

    return True

def add_participant_record(studydir, subject, age, sex): #copied from heudiconv, this solution is good b/c it checks if the same subject id is already exists
    participants_tsv = os.path.join(studydir, 'participants.tsv')
    participant_id = 'sub-%s' % subject

    if not create_file_if_missing(participants_tsv,'\t'.join(['participant_id', 'age', 'sex', 'group']) + '\n'):
        # check if may be subject record already exists
        with open(participants_tsv) as f:
            f.readline()
            known_subjects = {l.split('\t')[0] for l in f.readlines()}
        if participant_id in known_subjects:
            return
    # Add a new participant
    with open(participants_tsv, 'a') as f:
        f.write('\t'.join(map(str, [participant_id, age.lstrip('0').rstrip('Y') if age else 'N/A', sex, 'control'])) + '\n')

def create_file_if_missing(filename, content):
    """Create file if missing, so we do not
    override any possibly introduced changes"""
    if os.path.lexists(filename):
        return False
    dirname = os.path.dirname(filename)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    with open(filename, 'w') as f:
        f.write(content)
    return True

def bids_dcm_info(dcm_dir):
    """
    Extract relevant subject information from DICOM header
    - Assumes only one subject present within dcm_dir

    :param dcm_dir: directory containing all DICOM files or DICOM subfolders
    :return dcm_info: DICOM header information dictionary
    """

    # Init the DICOM structure
    ds = []

    # Init the subject info dictionary
    dcm_info = dict()

    # Walk through dcm_dir looking for valid DICOM files
    for subdir, dirs, files in os.walk(dcm_dir):
        for file in files:

            try:
                ds = pydicom.read_file(os.path.join(subdir, file))
            except:
                pass

            # Break out if valid DICOM read
            if ds:
                break

    if ds:

        # Fill dictionary
        # Note that DICOM anonymization tools sometimes clear these fields
        if hasattr(ds, 'PatientSex'):
            dcm_info['Sex'] = ds.PatientSex
        else:
            dcm_info['Sex'] = 'Unknown'

        if hasattr(ds, 'PatientAge'):
            dcm_info['Age'] = ds.PatientAge
        else:
            dcm_info['Age'] = 0

    else:

        print('* No DICOM header information found in %s' % dcm_dir)
        print('* Confirm that DICOM images in this folder are uncompressed')
        print('* Exiting')
        sys.exit(1)

    return dcm_info


def parse_dcm2niix_fname(fname):
    """
    Parse dcm2niix filename into values
    Filename format is '%n--%d--%q--%s' ie '<name>--<description>--<sequence>--<series #>'

    :param fname: str
        BIDS-style image or sidecar filename
    :return info: dict
    """

    # Ignore containing directory and extension(s)
    fname = strip_extensions(os.path.basename(fname))

    # Create info dictionary
    info = dict()

    # Split filename at '--'s
    vals = fname.split('--')

    info['SubjName'] = vals[0]
    info['SerDesc'] = vals[1]
    info['SeqName'] = vals[2]

    # Parse series string
    # eg '10' or '10_e2' or '10_e2_ph'
    ser_vals = vals[3].split('_')

    info['SerNo'] = ser_vals[0]
    if len(ser_vals) > 1:
        info['EchoNo'] = ser_vals[1]
    if len(ser_vals) > 2:
        info['IsPhase'] = True

    return info


def parse_bids_fname(fname):
    """
    Parse BIDS filename into key-value pairs

    :param fname:
    :return:
    """

    # Init return dictionary
    bids_keys = dict()

    # Retain only basename without extensions (handle .nii.gz)
    fname, _ = os.path.splitext(os.path.basename(fname))
    fname, _ = os.path.splitext(fname)

    kvs = fname.split('_')

    for kv in kvs:

        tmp = kv.split('-')

        if len(tmp) > 1:
            bids_keys[tmp[0]] = tmp[1]
        else:
            bids_keys['type'] = tmp[0]

    return bids_keys


def bids_add_run_number(bids_suffix, run_no):
    """
    Safely add run number to BIDS suffix
    Handle prior existence of run-* in BIDS filename template from protocol translator

    :param bids_suffix, str
    :param run_no, int
    :return: new_bids_suffix, str
    """

    if "run-" in bids_suffix:

        # Preserve existing run-* value in suffix
        print('  * BIDS suffix already contains run number - skipping')
        new_bids_suffix = bids_suffix

    else:

        if '_' in bids_suffix:

            # Add '_run-xx' before final suffix
            bmain, bseq = bids_suffix.rsplit('_', 1)
            new_bids_suffix = '%s_run-%02d_%s' % (bmain, run_no, bseq)

        else:

            # Isolated final suffix - just add 'run-xx_' as a prefix
            new_bids_suffix = 'run-%02d_%s' % (run_no, bids_suffix)

    return new_bids_suffix


def bids_events_template(bold_fname, overwrite=False):
    """
    Create a template events file for a corresponding BOLD imaging file
    :param bold_fname: str
        BOLD imaging filename (.nii.gz)
    :param overwrite: bool
        Overwrite flag
    :return: Nothing
    """
    if "_bold.nii.gz" in bold_fname: #can have sbref.nii.gz here and you do not want overwrite it
        events_fname = bold_fname.replace('_bold.nii.gz', '_events.tsv')
        events_bname = os.path.basename(events_fname)

        if os.path.isfile(events_fname):
            if overwrite:
                print('  Overwriting previous %s' % events_bname)
                create_file = True
            else:
                print('  Preserving previous %s' % events_bname)
                create_file = False
        else:
            print('  Creating %s' % events_fname)
            create_file = True

        if create_file:
            fd = open(events_fname, 'w')
            fd.write('onset\tduration\ttrial_type\tresponse_time\n')
            #fd.write('1.0\t0.5\tgo\t0.555\n')
            #fd.write('2.5\t0.4\tstop\t0.666\n')
            fd.close()


def strip_extensions(fname):
    """
    Remove one or more extensions from a filename
    :param fname:
    :return:
    """

    fstub, fext = os.path.splitext(fname)
    if fext == '.gz':
        fstub, fext = os.path.splitext(fstub)
    return fstub


def bids_load_prot_dict(prot_dict_json):
    """
    Read protocol translations from JSON file in DICOM directory

    :param prot_dict_json: string
        JSON protocol translation dictionary filename
    :return:
    """

    if os.path.isfile(prot_dict_json):

        # Read JSON protocol translator
        json_fd = open(prot_dict_json, 'r')
        prot_dict = json.load(json_fd)
        json_fd.close()

    else:

        prot_dict = dict()

    return prot_dict


def bids_fmap_echotimes(src_phase_json_fname):
    """
    Extract TE1 and TE2 from mag and phase MEGE fieldmap pairs

    :param src_phase_json_fname: str
    :return:
    """

    # Init returned TEs
    TE1, TE2 = 0.0, 0.0

    if os.path.isfile(src_phase_json_fname):

        # Read phase image metadata
        phase_dict = bids_read_json(src_phase_json_fname)

        # Populate series info dictionary from dcm2niix output filename
        info = parse_dcm2niix_fname(src_phase_json_fname)

        # Magnitude 1 series number is one less than phasediff series number
        mag1_ser_no = str(int(info['SerNo']) - 1)

        # Construct dcm2niix mag1 JSON filename
        # Requires dicm2niix v1.0.20180404 or later for echo number suffix '_e1'
        src_mag1_json_fname = info['SubjName'] +'--' +\
                              info['SerDesc'] + '--' +\
                              info['SeqName'] + '--' +\
                              mag1_ser_no + '_e1.json'
        src_mag1_json_path = os.path.join(os.path.dirname(src_phase_json_fname), src_mag1_json_fname)

        # Read mag1 metadata
        mag1_dict = bids_read_json(src_mag1_json_path)

        # Add TE1 key and rename TE2 key
        if mag1_dict:
            TE1 = mag1_dict['EchoTime']
            TE2 = phase_dict['EchoTime']
        else:
            print('*** Could not determine echo times multiecho fieldmap - using 0.0 ')

    else:

        print('* Fieldmap phase difference sidecar not found : ' + src_phase_json_fname)

    return TE1, TE2


def bids_create_prot_dict(prot_dict_json, prot_dict):
    """
    Write protocol translation dictionary template to JSON file
    :param prot_dict_json: string
        JSON filename
    :param prot_dict: dictionary
        Dictionary to write
    :return:
    """

    if os.path.isfile(prot_dict_json):

        print('* Protocol dictionary already exists : ' + prot_dict_json)
        print('* Skipping creation of new dictionary')

    else:

        json_fd = open(prot_dict_json, 'w')
        json.dump(prot_dict, json_fd, indent=4, separators=(',', ':'))
        json_fd.close()

        print('')
        print('---')
        print('New protocol dictionary created : %s' % prot_dict_json)
        print('Remember to replace "EXCLUDE" values in dictionary with an appropriate image description')
        print('For example "MP-RAGE T1w 3D structural" or "MB-EPI BOLD resting-state')
        print('---')
        print('')

    return


def bids_read_json(fname):
    """
    Safely read JSON sidecar file into a dictionary
    :param fname: string
        JSON filename
    :return: dictionary structure
    """

    try:
        fd = open(fname, 'r')
        json_dict = json.load(fd)
        fd.close()
    except:
        print('*** JSON sidecar not found - returning empty dictionary')
        json_dict = dict()

    return json_dict


def bids_write_json(fname, meta_dict, overwrite=False):
    """
    Write a dictionary to a JSON file. Account for overwrite flag
    :param fname: string
        JSON filename
    :param meta_dict: dictionary
        Dictionary
    :param overwrite: bool
        Overwrite flag
    :return:
    """

    bname = os.path.basename(fname)

    if os.path.isfile(fname):
        if overwrite:
            print('    Overwriting previous %s' % bname)
            create_file = True
        else:
            print('    Preserving previous %s' % bname)
            create_file = False
    else:
        print('    Creating new %s' % bname)
        create_file = True

    if create_file:
        with open(fname, 'w') as fd:
            json.dump(meta_dict, fd, indent=4, separators=(',', ':'))


def bids_auto_run_no(file_list):
    """
    Search for duplicate series names in dcm2niix output file list
    Return inferred run numbers accounting for duplication

    :param file_list: list of str
    :return: run_num, array of int
    """

    # Construct list of series descriptions and original numbers from file names
    ser_desc_list = []
    for fname in file_list:
        info = parse_dcm2niix_fname(fname)
        ser_desc_list.append(info['SerDesc'])

    # Find unique ser_desc entries using sets
    unique_descs = set(ser_desc_list)

    run_no = np.zeros(len(file_list))
    for desc in unique_descs:
        n = 1
        for i, ser_desc in enumerate(ser_desc_list):
            if ser_desc == desc:
                run_no[i] = n
                n += 1

    return run_no


def bids_build_intendedfor(SID, SES, bids_suffix):
    """
    Build the IntendedFor entry for a fieldmap sidecar

    :param SID, str : Subject ID
    :param SES, str : Session number
    :param bids_suffix:
    :return: ifstr, str
    """
    bids_name = os.path.basename(bids_suffix)
    bids_type = os.path.dirname(bids_suffix)
    if bids_type == '':
        bids_type = 'func'

    # Complete BIDS filenames for image and sidecar
    if SES:
        # If sessions are being used, add session directory to IntendedFor field
        ifstr = os.path.join('ses-'+SES, bids_type, 'sub-'+SID+'_ses-'+SES+'_'+bids_name+'.nii.gz')
    else:
        ifstr = os.path.join(bids_type, 'sub-'+SID+'_'+bids_name+'.nii.gz')


    return ifstr


def safe_mkdir(dname):
    """
    Safely create a directory path
    :param dname: string
    :return:
    """

    if not os.path.isdir(dname):
        os.makedirs(dname, exist_ok=True)


def safe_copy(fname1, fname2, overwrite=False):
    """
    Copy file accounting for overwrite flag
    :param fname1: str
    :param fname2: str
    :param overwrite: bool
    :return:
    """

    bname1, bname2 = os.path.basename(fname1), os.path.basename(fname2)

    if os.path.isfile(fname2):
        if overwrite:
            print('    Copying %s to %s (overwrite)' % (bname1, bname2))
            create_file = True
        else:
            print('    Preserving previous %s' % bname2)
            create_file = False
    else:
        print('    Copying %s to %s' % (bname1, bname2))
        create_file = True

    if create_file:
        shutil.copy(fname1, fname2)

def bids_add_intended_run(prot_dict, info, run_no):
    """
    Add run numbers to files in IntendedFor.
    :param prot_dict: dict
    :param info: dict
    :param run_no: int
    :return prot_dict: dict
    """

    prot_dict_update = dict()
    for k in prot_dict.keys():
        if prot_dict[k][0] == 'fmap':
            # get a list of the intended runs
            intended_for = prot_dict[k][2]
            if type(prot_dict[k][2]) == list:
                intended_for = prot_dict[k][2]
            elif prot_dict[k][2] != 'UNASSIGNED':
                intended_for = [prot_dict[k][2]]
            else:
                break

            suffixes = [os.path.basename(x) for x in intended_for]
            types = [os.path.dirname(x) for x in intended_for]

            # determine if this sequence is intended by the fmap
            if prot_dict[info['SerDesc']] in suffixes:
                idx = suffixes.index(prot_dict[info['SerDesc']][1])

                # change intendedfor to include run or add a new run
                new_suffix = bids_add_run_number(suffixes[idx], run_no)

                if new_suffix != suffixes[idx]:
                    if '_run-' in suffixes[idx]:
                        suffixes.append(new_suffix)
                        types.append(types[idx])
                    else:
                        suffixes[idx] = new_suffix

                intended_for = [os.path.join(x[0], x[1]) for x in zip(types, suffixes)]
                prot_dict_update[k] = ['fmap', prot_dict[k][1], intended_for]

    prot_dict.update(prot_dict_update)
    return prot_dict



# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
