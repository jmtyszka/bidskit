#!/usr/bin/env python3
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

__version__ = '0.9.2'

import os
import sys
import argparse
import subprocess
import shutil
import json
import pydicom
from glob import glob


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')
    parser.add_argument('-i','--indir', required=True, help='DICOM input directory with Subject/Session/Image organization')
    parser.add_argument('-o','--outdir', required=True, help='Output BIDS directory root')
    parser.add_argument('--use_run', action='store_true', default=False, help='Add run number to filename')

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

            # Check is subject/session directory exists
            # If it doesn't this is a new sub/ses added to the DICOM root and needs conversion

            # Safely create BIDS conversion directory and all containing directories as needed
            os.makedirs(bids_conv_dir, exist_ok=True)

            if first_pass:

                # Run dcm2niix conversion into temporary conversion directory
                # This relies on the current CBIC branch of dcm2niix which extracts additional DICOM fields
                print('  Converting all DICOM images within directory %s' % dcm_ses_dir)
                devnull = open(os.devnull, 'w')
                subprocess.call(['dcm2niix', '-b', 'y', '-f', '%n--%p--%q--%s', '-o', bids_conv_dir, dcm_ses_dir],
                                stdout=devnull, stderr=subprocess.STDOUT)

            else:

                # Get subject age and sex from representative DICOM header
                dcm_info = bids_dcm_info(dcm_ses_dir)

                # Add line to participants TSV file
                participants_fd.write("%s\t%s\t%s\n" % (SID, dcm_info['Sex'], dcm_info['Age']))

            # Run DICOM conversions
            bids_run_conversion(bids_conv_dir, first_pass, prot_dict, bids_ses_dir, SID, use_run)

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


def bids_run_conversion(conv_dir, first_pass, prot_dict, sid_dir, SID, use_run):
    """

    :param conv_dir:
    :param first_pass:
    :param prot_dict:
    :param sid_dir:
    :param SID:
    :param use_run: flag to add run key-value to filenames [False]
    :return:
    """

    if os.path.isdir(conv_dir):

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        # glob returns the full relative path from the tmp dir
        for src_nii_fname in glob(os.path.join(conv_dir, '*.nii*')):

            # Parse image filename into fields
            subj_name, prot_name, seq_name, ser_no = bids_parse_filename(src_nii_fname)

            # Check if we're creating new protocol dictionary
            if first_pass:

                print('  Adding protocol %s to dictionary template' % prot_name)

                # Add current protocol to protocol dictionary
                # The value defaults to "EXCLUDE" which should be replaced with the correct NDAR
                # ImageDescription for this protocol (eg "T1w Structural", "BOLD MB EPI Resting State")
                prot_dict[prot_name] = ["EXCLUDE_BIDS_Name", "EXCLUDE_BIDS_Directory"]

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

                # Skip excluded protocols
                if prot_dict[prot_name][0].startswith('EXCLUDE'):

                    print('* Excluding protocol ' + prot_name)

                else:

                    print('  Organizing ' + prot_name)

                    # Use protocol dictionary to determine destination folder and image/sidecar name
                    bids_stub, bids_dir = prot_dict[prot_name]

                    # Add the DICOM series number as a run number
                    # TODO: Work out a better way to handle duplicate runs with identical protocol names
                    if use_run:
                        bids_stub = bids_run_number(bids_stub, ser_no)

                    # Create BIDS purpose directory
                    bids_purpose_dir = os.path.join(sid_dir, bids_dir)
                    if not os.path.isdir(bids_purpose_dir):
                        os.makedirs(bids_purpose_dir, exist_ok=True)

                    # Complete BIDS filenames for image and sidecar
                    bids_nii_fname = os.path.join(bids_purpose_dir, 'sub-' + SID + '_' + bids_stub + '.nii.gz')
                    bids_json_fname = os.path.join(bids_purpose_dir, 'sub-' + SID + '_' + bids_stub + '.json')

                    # Special handling for specific purposes (anat, func, fmap, etc)
                    bids_nii_fname, bids_json_fname = bids_purpose_handling(bids_dir, seq_name, ser_no,
                                                                            bids_nii_fname, bids_json_fname,
                                                                            src_json_fname)

                    # Move image and sidecar to BIDS purpose directory
                    # Use empty filename to skip surplus fieldmap images and sidecars

                    if bids_nii_fname:
                        print('    Copying %s to %s' % (src_nii_fname, bids_nii_fname))
                        shutil.copy(src_nii_fname, bids_nii_fname)

                    if bids_json_fname:
                        print('    Copying %s to %s' % (src_json_fname, bids_json_fname))
                        shutil.copy(src_json_fname, bids_json_fname)

        # Cleanup temporary working directory after Pass 2
        if not first_pass:
            print('  Cleaning up temporary files')
            shutil.rmtree(conv_dir)


def bids_purpose_handling(bids_dir, seq_name, ser_no, bids_nii_fname, bids_json_fname, src_json_fname):
    """
    Special handling for each image purpose

    :param bids_dir:
    :return:
    """

    # Load the JSON sidecar
    info = bids_read_json(src_json_fname)

    if bids_dir == 'func':

        if seq_name == 'EP':
            print('    EPI detected')
            print('    Creating events template file')
            bids_events_template(bids_nii_fname)

    elif bids_dir == 'fmap':

        # Check for MEGE vs SE-EPI fieldmap images
        # MEGE will have a 'GR' sequence, SE-EPI will have 'EP'

        print('    Identifying fieldmap image type')
        if seq_name == 'GR':

            print('    GRE detected')
            print('    Identifying magnitude and phase images')

            # For Siemens GRE fieldmaps, there will be three images in two series
            # The "_e2" suffix is generated by dcm2niix
            # *_<ser_no>.nii.gz : TE1 mag
            # *_<ser_no>_e2.nii.gz : TE2 mag
            # *_<ser_no+1>_e2.nii.gz : TE2-TE1 phase difference

            if ser_no.endswith('_e2'):

                # Read phase meta data
                if '_P_' in info['ImageType']:

                    print('    Phase difference image')
                    bids_nii_fname = bids_nii_fname.replace('.nii.gz', '_phasediff.nii.gz')
                    bids_json_fname = bids_json_fname.replace('.json', '_phasediff.json')

                    # Update the phase difference sidecar with TE1 as per BIDS spec
                    bids_update_fmap_sidecar(src_json_fname)

                else:

                    print('    Echo 2 magnitude - discarding')
                    bids_nii_fname = []  # Discard image
                    bids_json_fname = []  # Discard sidecar

            else:

                print('    Echo 1 magnitude')
                bids_nii_fname = bids_nii_fname.replace('.nii.gz', '_magnitude1.nii.gz')
                bids_json_fname = []  # Discard sidecar only

        elif seq_name == 'EP':

            print('    EPI detected')

        else:

            print('    Unrecognized fieldmap detected')
            print('    Simply copying image and sidecar to fmap directory')

    elif bids_dir == 'anat':

        if seq_name == 'GR_IR':

            print('    IR-prepared GRE detected - likely T1w MP-RAGE or equivalent')

        elif seq_name == 'SE':

            print('    Spin echo detected - likely T1w or T2w anatomic image')

        elif seq_name == 'GR':

            print('    Gradient echo detected')


    return bids_nii_fname, bids_json_fname


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
    :param dcm_sub_dir:
    :return dcm_info: DICOM header information dictionary
    """

    # Loop over files until first valid DICOM is found
    ds = []
    for dcm in os.listdir(dcm_dir):
        try:
            ds = pydicom.read_file(os.path.join(dcm_dir, dcm))
        except:
            pass

        # Break out if valid DICOM read
        if ds:
            break

    # Init a new dictionary
    dcm_info = dict()

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


def bids_parse_filename(fname):
    """
    Parse dcm2niix filename into values
    Filename format is '%n--%p--%q--%s' ie '<name>--<protocol>--<sequence>--<series #>'
    dcm2niix will add the '_e2' suffix to the series # for multiecho sequences such as GRE fieldmaps
    :param fname: BIDS-style image or sidecar filename
    :return subj_name, prot_name, seq_name, ser_no:
    """

    # Ignore containing directory and extension(s)
    fname = strip_extensions(os.path.basename(fname))

    # Split filename at '--'s
    vals = fname.split('--')
    subj_name = vals[0]
    prot_name = vals[1]
    seq_name = vals[2]
    ser_no = vals[3]

    return subj_name, prot_name, seq_name, ser_no


def bids_run_number(bids_stub, ser_no):

    # Eliminate unused suffix from ser_no if present (eg '_e2')
    if '_' in ser_no:
        ser_no, _ = ser_no.split('_',1)

    if '_' in bids_stub:
        # Add '_run-xx' before final suffix
        bmain, bseq = bids_stub.rsplit('_',1)
        new_bids_stub = '%s_run-%02d_%s' % (bmain, int(ser_no), bseq)
    else:
        # Isolated final suffix - just add 'run-xx_' as a prefix
        new_bids_stub = 'run-%02d_%s' % (int(ser_no), bids_stub)

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
        prot_trans = json.load(json_fd)
        json_fd.close()

    else:

        prot_trans = dict()

    return prot_trans


def bids_update_fmap_sidecar(json_phase_fname):
    """
    Update the fmap phase difference sidecar with TE1
    :param json_fname:
    :return:
    """

    if os.path.isfile(json_phase_fname):

        # Read phase metadata
        phase_dict = bids_read_json(json_phase_fname)

        # Parse filename into fields
        subj_name, prot_name, seq_name, ser_no = bids_parse_filename(json_phase_fname)

        # Strip _e2 suffix and subtract 1 for mag1 series number
        TE2_ser_no = ser_no.replace('_e2', '')
        TE1_ser_no = str(int(TE2_ser_no) - 1)

        # Construct mag1 JSON filename
        mag1_fname = subj_name + '--' + prot_name + '--' + seq_name + '--' + TE1_ser_no + '.json'
        json_mag1_fname = os.path.join(os.path.dirname(json_phase_fname), mag1_fname)

        # Read mag1 metadata
        mag1_dict = bids_read_json(json_mag1_fname)

        # Add TE1 key and rename TE2 key
        if mag1_dict:
            phase_dict['EchoTime1'] = mag1_dict['EchoTime']
            phase_dict['EchoTime2'] = phase_dict.pop('EchoTime')
        else:
            print('*** Could not determine echo times for fieldmap')
            phase_dict['EchoTime1'] = '-1.0'
            phase_dict['EchoTime2'] = '-1.0'

        # Resave phase image metadata
        bids_write_json(json_phase_fname, phase_dict)

    else:

        print('* Fieldmap phase difference sidecar not found : ' + json_phase_fname)

    return


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
