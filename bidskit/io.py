"""
Utility functions for handling creation, writing, reading and parsing of BIDS files

MIT License

Copyright (c) 2017-2021 Mike Tyszka

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
import shutil
import json
import pydicom
import numpy as np


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
        print('*** {}'.format(fname))
        print('*** JSON sidecar not found - returning empty dictionary')
        json_dict = dict()
    except json.decoder.JSONDecodeError:
        print('*** {}'.format(fname))
        print('*** JSON sidecar decoding error - returning empty dictionary')
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
            except Exception as err:
                # Silently skip problem files in DICOM directory
                continue

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
    Filename format is '%n--%d--%q--%s' ie '<name>--<description>--<sequence>--<series no>'

    NOTES:
    - Multiple series generated by single acquisition (eg multiecho fieldmaps, localizers, etc) are
      handled through the dcm2niix extensions (_e1, e2_ph, _i00001, etc).
    - Series number resets following subject re-landmarking make the SerNo useful only for
      determining series uniqueness and not for ordering or run numbering.
    - See also bidskit.translate.auto_run_no()

    Current dcm2niix version : v20200331

    :param fname: str, BIDS-style image or sidecar filename
    :return info: dict
    """

    # Create info dictionary
    info = dict()

    # Parent directory
    info['DirName'] = os.path.dirname(fname)

    # Strip parent directory and extension(s)
    fname, fext = strip_extensions(os.path.basename(fname))

    # Split filename at '--'s
    vals = fname.split('--')

    info['SubjName'] = vals[0]
    info['SerDesc'] = vals[1]
    info['SeqName'] = vals[2]

    # Handle series number and possible suffices, which include
    # _e%d    : echo magnitude images (eg _e1, _e2)
    # _e%d_ph : echo phase or phase difference images (eg _e2_ph)
    # _i%05d  : images with differing orientations (eg _i00001) from multiplane localizer scans

    # Separate series number from suffix (underscore separated)
    # Handle both (eg) '10_e1' and '9_e1_ph'
    bits = vals[3].split('_', 1)
    info['SerNo'] = bits[0]
    if len(bits) > 1:
        info['Suffix'] = bits[1]
    else:
        info['Suffix'] = ''

    return info


def parse_bids_fname(fname):
    """
    Parse BIDS filename into key-value pairs

    :param fname: str,
        Raw BIDS-format filename with extension(s)
    :return: dict,
        Dictionary of key-value pairs parsed from BIDS-format filename
    """

    # Init return dictionary with BIDS 1.1.1 valid key strings
    bids_keys = {
        'sub': "",
        'ses': "",
        'task': "",
        'run': "",
        'acq': "",
        'dir': "",
        'ce': "",
        'rec': "",
        'mod': "",
        'echo': "",
        'proc': "",
        'suffix': "",
    }

    # Extract base filename and strip up to two extensions
    # Accounts for both '.nii' and '.nii.gz' variants
    fname, _ = os.path.splitext(os.path.basename(fname))
    fname, _ = os.path.splitext(fname)

    # Locate, record and remove final constrast suffix
    suffix_start = fname.rfind('_') + 1
    bids_keys['suffix'] = fname[suffix_start:]
    fname = fname[:suffix_start]

    # Divide filename into keys and values
    # Value segments are delimited by '<key>-' strings

    key_name = []
    val_start = []
    key_start = []

    # Search for any valid keys in filename
    # Record key and value start indices within string
    for key in bids_keys:

        key_str = key + '-'

        i0 = fname.find(key_str)
        if i0 > -1:
            i1 = i0 + len(key_str)
            key_name.append(key)
            key_start.append(i0)
            val_start.append(i1)

    # Convert lists to numpy arrays
    key_name = np.array(key_name)
    key_start = np.array(key_start)
    val_start = np.array(val_start)

    # Sort keys by position in filename
    key_order = np.argsort(key_start)
    key_name_sorted = key_name[key_order]
    val_start_sorted = val_start[key_order]
    val_end_sorted = key_start[np.roll(key_order, -1)] - 1

    # Fill BIDS key-value dictionary
    for kc in range(len(key_name_sorted)):

        kname = key_name_sorted[kc]
        vstart = val_start_sorted[kc]
        vend = val_end_sorted[kc]
        val = fname[vstart:vend]
        bids_keys[kname] = val

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
        fstub, fext2 = os.path.splitext(fstub)
        fext = fext2 + fext
    return fstub, fext


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