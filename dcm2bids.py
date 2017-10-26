#!/usr/bin/env python
"""
Convert flat DICOM file set into a BIDS-compliant Nifti structure

The DICOM input directory should be organized as follows:
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

Usage
----
dcm2bids.py -i <DICOM Directory> -o <BIDS Directory Root>

Example
----
% dcm2bids.py -i mydicom -o mybids

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2016-08-03 JMT From scratch
2016-11-04 JMT Add session directory to DICOM heirarchy

MIT License

Copyright (c) 2016 Mike Tyszka

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

__version__ = '0.9.4'

import os
import sys
import argparse
import subprocess
import shutil
import json
import dicom
from glob import glob


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')
    parser.add_argument('-i','--indir', default='dicom', help='DICOM input directory with Subject/Session/Image organization [dicom]')
    parser.add_argument('-o','--outdir', default='source', help='Output BIDS source directory [source]')
    parser.add_argument('--use_run', action='store_true', default=False, help='Add run number to BIDS filename [False]')

    # Parse command line arguments
    args = parser.parse_args()

    dcm_root_dir = args.indir
    bids_root_dir = args.outdir
    use_run = args.use_run

    # Load protocol translation and exclusion info from DICOM directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the DICOM directory. This template should be
    # completed by the user and the conversion rerun.
    prot_dict_json = os.path.join(dcm_root_dir, 'Protocol_Translator.json')
    prot_dict = bids_load_prot_dict(prot_dict_json)

    if prot_dict and os.path.isdir(bids_root_dir):
        print('')
        print('------------------------------------------------------------')
        print('Pass 2 : Organizing Nifti data into BIDS directories')
        print('------------------------------------------------------------')
        first_pass = False
    else:
        print('')
        print('------------------------------------------------------------')
        print('Pass 1 : DICOM to Nifti conversion and dictionary creation')
        print('------------------------------------------------------------')
        first_pass = True

    # Initialize BIDS output directory
    if not first_pass:
        participants_fd = bids_init(bids_root_dir)

    # Loop over subject directories in DICOM root
    for dcm_sub_dir in glob(dcm_root_dir + '/*/'):

        SID = os.path.basename(dcm_sub_dir.strip('/'))

        print('')
        print('Processing subject ' + SID)

        # Loop over session directories in subject directory
        for dcm_ses_dir in glob(dcm_sub_dir + '/*/'):

            SES = os.path.basename(dcm_ses_dir.strip('/'))

            print('  Processing session ' + SES)

            # BIDS subject, session and conversion directories
            sub_prefix = 'sub-' + SID
            ses_prefix = 'ses-' + SES
            bids_sub_dir = os.path.join(bids_root_dir, sub_prefix)
            bids_ses_dir = os.path.join(bids_sub_dir, ses_prefix)
            bids_conv_dir = os.path.join(bids_ses_dir, 'conv')

            # Check if subject/session directory exists
            # If it doesn't this is a new sub/ses added to the DICOM root and needs conversion

            # Safely create BIDS conversion directory and all containing directories as needed
            if not os.path.isdir(bids_conv_dir):
                os.makedirs(bids_conv_dir)
                needs_converting = True
            else:
                needs_converting = False

            if first_pass or needs_converting:

                # Run dcm2niix conversion into temporary conversion directory
                print('  Converting all DICOM images within directory %s' % dcm_ses_dir)
                devnull = open(os.devnull, 'w')
                subprocess.call(['dcm2niix', '-b', 'y', '-z', 'y', '-f', '%n--%d--%q--%s',
                                 '-o', bids_conv_dir, dcm_ses_dir],
                                stdout=devnull, stderr=subprocess.STDOUT)

            else:

                # Get subject age and sex from representative DICOM header
                dcm_info = bids_dcm_info(dcm_ses_dir)

                # Add line to participants TSV file
                participants_fd.write("sub-%s\t%s\t%s\n" % (SID, dcm_info['Sex'], dcm_info['Age']))

            # Run DICOM conversions
            bids_run_conversion(bids_conv_dir, first_pass, prot_dict, bids_ses_dir, SID, SES, use_run)

    if first_pass:
        # Create a template protocol dictionary
        bids_create_prot_dict(prot_dict_json, prot_dict)
    else:
        # Close participants TSV file
        participants_fd.close()

    # Clean exit
    sys.exit(0)


def bids_listdir(dname):
    """
    Return list of non-hidden subdirectories of a given directory

    :param dname:
    :return:
    """

    return


def bids_run_conversion(conv_dir, first_pass, prot_dict, sid_dir, SID, SES, use_run):
    """

    :param conv_dir:
    :param first_pass:
    :param prot_dict:
    :param sid_dir:
    :param SID: subject ID
    :param SES: session name or number
    :param use_run: flag to add run key-value to filenames [False]
    :return:
    """

    # Temporary flags
    do_cleanup = False

    if os.path.isdir(conv_dir):

        # glob returns the full relative path from the tmp dir
        filelist = glob(os.path.join(conv_dir, '*.nii*'))
        
        # Determine where we have runs with the same description (name)
        run_suffix=[0] * len(filelist)
        for file_index in range(len(filelist)-1):
            src_nii_fname = filelist[file_index]
            subj_name, ser_desc, seq_name, ser_no = parse_dcm2niix_fname(src_nii_fname)
            matches = [i for i in range(len(filelist)) if ser_desc in filelist[i]]
            if len(matches) > 1:
                for i in matches:
                    run_suffix[i]=i-min(matches)+1  #Yes, this will re-create this little list several times and no, that's not ideal

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        file_index = 0
        for src_nii_fname in filelist:

            # Parse image filename into fields
            subj_name, ser_desc, seq_name, ser_no = parse_dcm2niix_fname(src_nii_fname)

            # Check if we're creating new protocol dictionary
            if first_pass:

                print('  Adding protocol %s to dictionary template' % ser_desc)

                # Add current protocol to protocol dictionary
                # Use default EXCLUDE_* values which can be changed (or not) by the user
                prot_dict[ser_desc] = ["EXCLUDE_BIDS_Directory", "EXCLUDE_BIDS_Name"]

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

                if prot_dict[ser_desc][0].startswith('EXCLUDE'):

                    # Skip excluded protocols
                    print('* Excluding protocol ' + ser_desc)

                else:

                    print('  Organizing ' + ser_desc)

                    # Use protocol dictionary to determine purpose folder and BIDS filename suffix
                    bids_purpose, bids_suffix  = prot_dict[ser_desc]

                    # Add the DICOM series number as a run number
                    # TODO: Work out a better way to handle duplicate runs with identical protocol names
                    if use_run:
                        bids_suffix = bids_add_run_number(bids_suffix, ser_no)
                    if run_suffix[file_index]:
                        bids_suffix = bids_add_run_number(bids_suffix, str(run_suffix[file_index]))
                    # Create BIDS purpose directory
                    bids_purpose_dir = os.path.join(sid_dir, bids_purpose)
                    if not os.path.isdir(bids_purpose_dir):
                        os.makedirs(bids_purpose_dir)

                    # Complete BIDS filenames for image and sidecar
                    bids_nii_fname = os.path.join(bids_purpose_dir, 'sub-' + SID + '_ses-' + SES + '_' + bids_suffix + '.nii.gz')
                    bids_json_fname = bids_nii_fname.replace('.nii.gz','.json')

                    # Special handling for specific purposes (anat, func, fmap, etc)
                    # This function populates BIDS structure with the image and adjusted sidecar
                    bids_purpose_handling(bids_purpose, seq_name,
                                          src_nii_fname, src_json_fname,
                                          bids_nii_fname, bids_json_fname)
            file_index += 1

        # Cleanup temporary working directory after Pass 2
        if not first_pass:
            if do_cleanup:
                print('  Cleaning up temporary files')
                shutil.rmtree(conv_dir)
            else:
                print('  Preserving conversion directory')


def bids_purpose_handling(bids_purpose, seq_name, src_nii_fname, src_json_fname, bids_nii_fname, bids_json_fname):
    """
    Special handling for each image purpose

    :param bids_purpose:
    :param seq_name:
    :param src_nii_fname:
    :param src_json_fname:
    :param bids_nii_fname:
    :param bids_json_fname:
    :return:
    """

    # Load the JSON sidecar
    info = bids_read_json(src_json_fname)

    if bids_purpose == 'func':

        if seq_name == 'EP':

            print('    EPI detected')
            print('      Creating events template file')
            bids_events_template(bids_nii_fname)

            # Add taskname to BIDS JSON sidecar
            bids_keys = parse_bids_fname(bids_nii_fname)
            if 'task' in bids_keys:
                info['TaskName'] = bids_keys['task']
            else:
                info['TaskName'] = 'unknown'

    elif bids_purpose == 'fmap':

        # Check for MEGE vs SE-EPI fieldmap images
        # MEGE will have a 'GR' sequence, SE-EPI will have 'EP'

        print('    Identifying fieldmap image type')
        if seq_name == 'GR':

            print('    GRE detected')
            print('    Identifying magnitude and phase images')

            # 2017-06-26 JMT Adapt to changes in dcm2niix JSON sidecar
            # For Siemens dual gradient echo fieldmaps, three Nifti/JSON pairs are generated from two series
            # *--GR--<serno>.<ext> : magnitude image from echo 1 (EchoNumber unset, ImageType[2] = "M")
            # *--GR--<serno>a.<ext> : magnitude image from echo 2 (EchoNumber = 2, ImageType[2] = "M")
            # *--GR--<serno+1>.<ext> : inter-echo phase difference (EchoNumber = 2, ImageType[2] = "P")

            if 'EchoNumber' in info:

                if info['EchoNumber'] == 2:

                    if 'P' in info['ImageType'][2]:

                        # Read phase meta data
                        bids_nii_fname = bids_nii_fname.replace('.nii.gz', '_phasediff.nii.gz')
                        bids_json_fname = bids_json_fname.replace('.json', '_phasediff.json')

                        # Extract TE1 and TE2 from mag and phase JSON sidecars
                        TE1, TE2 = bids_fmap_echotimes(src_json_fname)
                        info['EchoTime1'] = TE1
                        info['EchoTime2'] = TE2

                    else:

                        # Echo 2 magnitude - discard
                        print('    Echo 2 magnitude - discarding')
                        bids_nii_fname = []  # Discard image
                        bids_json_fname = []  # Discard sidecar

            else:

                print('    Echo 1 magnitude')
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


    # Write BIDS Nifti image and JSON sidecar
    print('  Writing image and sidecar to BIDS structure')

    if bids_nii_fname:
        print('    Copying %s to %s' % (src_nii_fname, bids_nii_fname))
        shutil.copy(src_nii_fname, bids_nii_fname)

    if bids_json_fname:
        print('    Writing JSON sidecar to %s' % bids_json_fname)
        bids_write_json(bids_json_fname, info)


def bids_init(bids_root_dir):
    """
    Initialize root BIDS directory
    :param bids_root_dir: root BIDS directory
    :return participants_fd: participant TSV file descriptor
    """

    # Create template participant TSV file in BIDS root directory
    parts_tsv = os.path.join(bids_root_dir, 'participants.tsv')
    participants_fd = open(parts_tsv, 'w')
    participants_fd.write('participant_id\tsex\tage\n')

    # Create template JSON dataset description
    datadesc_json = os.path.join(bids_root_dir, 'dataset_description.json')
    meta_dict = dict({'BIDSVersion': "1.0.0",
               'License': "This data is made available under the Creative Commons BY-SA 4.0 International License.",
               'Name': "The dataset name goes here",
               'ReferencesAndLinks': "References and links for this dataset go here"})

    # Write JSON file
    bids_write_json(datadesc_json, meta_dict)

    return participants_fd


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
                ds = dicom.read_file(os.path.join(subdir, file))
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
    :param fname: BIDS-style image or sidecar filename
    :return subj_name, ser_desc, seq_name, ser_no:
    """

    # Ignore containing directory and extension(s)
    fname = strip_extensions(os.path.basename(fname))

    # Split filename at '--'s
    vals = fname.split('--')
    subj_name = vals[0]
    ser_desc = vals[1]
    seq_name = vals[2]
    ser_no = vals[3]

    return subj_name, ser_desc, seq_name, ser_no


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


def bids_add_run_number(bids_stub, ser_no):
    """
    Add run number to BIDS filename

    :param bids_stub:
    :param ser_no:
    :return:
    """

    # Discard non-numeric characters in ser_no
    ser_no = int(''.join(filter(str.isdigit, ser_no)))

    if '_' in bids_stub:
        # Add '_run-xx' before final suffix
        bmain, bseq = bids_stub.rsplit('_',1)
        new_bids_stub = '%s_run-%02d_%s' % (bmain, ser_no, bseq)
    else:
        # Isolated final suffix - just add 'run-xx_' as a prefix
        new_bids_stub = 'run-%02d_%s' % (ser_no, bids_stub)

    return new_bids_stub


def bids_catch_duplicate(fname):
    """
    Add numeric suffix if filename already exists
    :param fname: original filename
    :return new_fname: new filename
    """

    new_fname = fname

    fpath, fbase = os.path.split(fname)
    fstub, fext = fbase.split('.', 1)

    n = 1

    while os.path.isfile(new_fname):

        n += 1

        new_fname = os.path.join(fpath, fstub + '_' + str(n) + '.' + fext)

    return new_fname

def bids_events_template(bold_fname):
    """
    Create a template events file for a corresponding BOLD imaging file
    :param bold_fname: BOLD imaging filename (.nii.gz)
    :return: Nothing
    """

    events_fname = bold_fname.replace('_bold.nii.gz', '_events.tsv')

    fd = open(events_fname, 'w')
    fd.write('onset\tduration\ttrial_type\tresponse_time\n')
    fd.write('1.0\t0.5\tgo\t0.555\n')
    fd.write('2.5\t0.4\tstop\t0.666\n')
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
    :param prot_dict_json:
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

    :param src_phase_json_fname:
    :return:
    """

    # Init returned TEs
    TE1, TE2 = 0.0, 0.0

    if os.path.isfile(src_phase_json_fname):

        # Read phase image metadata
        phase_dict = bids_read_json(src_phase_json_fname)

        # Parse dcm2niix filename into fields
        subj_name, prot_name, seq_name, ser_no = parse_dcm2niix_fname(src_phase_json_fname)

        # Magnitude 1 series number is one less than phasediff series number
        mag1_ser_no = str(int(ser_no) - 1)

        # Construct dcm2niix mag1 JSON filename
        src_mag1_json_fname = subj_name + '--' + prot_name + '--' + seq_name + '--' + mag1_ser_no + '.json'
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
    :param prot_dict_json:
    :param prot_dict:
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
    '''
    Safely read JSON sidecar file into a dictionary
    :param fname: JSON filename
    :return: dictionary structure
    '''

    try:
        fd = open(fname, 'r')
        json_dict = json.load(fd)
        fd.close()
    except:
        print('*** JSON sidecar not found - returning empty dictionary')
        json_dict = dict()

    return json_dict


def bids_write_json(fname, meta_dict):
    with open(fname, 'w') as fd:
        json.dump(meta_dict, fd, indent=4, separators=(',', ':'))


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
