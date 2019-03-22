"""
Utility functions for handling creation, writing, reading and parsing of BIDS files
"""

import os
import sys
import shutil
import json
import pydicom


def read_json(fname):
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
    except IOError:
        print('*** JSON sidecar not found - returning empty dictionary')
        json_dict = dict()

    return json_dict


def write_json(fname, meta_dict, overwrite=False):
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


def events_template(bold_fname, overwrite=False):
    """
    Create a template events file for a corresponding BOLD imaging file

    :param bold_fname: str, BOLD imaging filename (.nii.gz)
    :param overwrite: bool, Overwrite flag
    :return: Nothing
    """

    # Can have sbref.nii.gz here and you do not want overwrite it
    if "_bold.nii.gz" in bold_fname:
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
            fd.close()


def dcm_info(dcm_dir):
    """
    Extract relevant subject information from DICOM header
    - Assumes only one subject present within dcm_dir

    :param dcm_dir: directory containing all DICOM files or DICOM subfolders
    :return info_dict: DICOM header information dictionary
    """

    # Init the DICOM structure
    ds = []

    # Init the subject info dictionary
    info_dict = dict()

    # Walk through dcm_dir looking for valid DICOM files
    for subdir, dirs, files in os.walk(dcm_dir):
        for file in files:

            try:
                ds = pydicom.read_file(os.path.join(subdir, file))
            except IOError:
                pass

            # Break out if valid DICOM read
            if ds:
                break

    if ds:

        # Fill dictionary
        # Note that DICOM anonymization tools sometimes clear these fields
        if hasattr(ds, 'PatientSex'):
            info_dict['Sex'] = ds.PatientSex
        else:
            info_dict['Sex'] = 'Unknown'

        if hasattr(ds, 'PatientAge'):
            info_dict['Age'] = ds.PatientAge
        else:
            info_dict['Age'] = 0

    else:

        print('* No DICOM header information found in %s' % dcm_dir)
        print('* Confirm that DICOM images in this folder are uncompressed')
        print('* Exiting')
        sys.exit(1)

    return info_dict


def parse_dcm2niix_fname(fname):
    """
    Parse dcm2niix filename into values
    Filename format is '%n--%d--%q--%t' ie '<name>--<description>--<sequence>--<time>'

    :param fname: str, BIDS-style image or sidecar filename
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
    info['AcqTime'] = vals[3]

    # # Parse time string
    # ser_vals = vals[3].split('_')
    #
    # info['SerNo'] = ser_vals[0]
    # if len(ser_vals) > 1:
    #     info['EchoNo'] = ser_vals[1]
    # if len(ser_vals) > 2:
    #     info['IsPhase'] = True

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


def create_file_if_missing(filename, content):
    """
    Create file if missing, so we do not override any possibly introduced changes

    :param filename:
    :param content:
    :return:
    """

    if os.path.lexists(filename):
        return False

    dirname = os.path.dirname(filename)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    with open(filename, 'w') as f:
        f.write(content)

    return True


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


def nii_to_json(nii_fname):
    """
    Replace Nifti extension ('.nii.gz' or '.nii') with '.json'

    :param nii_fname:
    :return: json_fname
    """
    if '.nii.gz' in nii_fname:
        json_fname = nii_fname.replace('.nii.gz', '.json')
    elif 'nii' in nii_fname:
        json_fname = nii_fname.replace('.nii', '.json')
    else:
        print('* Unknown extension for %s' % nii_fname)
        json_fname = nii_fname + '.json'

    return json_fname