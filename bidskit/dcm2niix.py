"""
Utility functions for working with dcm2niix output in the work/ folder

MIT License
Copyright (c) 2017-2022 Mike Tyszka
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
import re
import subprocess
import shutil
import copy
from glob import glob

from . import io as bio
from . import translate as tr
from . import fmaps
from .json import (get_acq_time)


def ordered_file_list(conv_dir, nii_ext):
    """
    Generated list of dcm2niix Nifti output files ordered by acquisition time
    :param conv_dir: str, working conversion directory
    :return:
    """

    # Get Nifti image list from conversion directory
    nii_list = sorted(glob(os.path.join(conv_dir, '*.nii*')))

    # Derive JSON sidecar list
    json_list = [bio.nii_to_json(nii_file, nii_ext) for nii_file in nii_list]

    # Pull acquisition times for each Nifti image from JSON sidecar
    acq_time = [get_acq_time(json_file) for json_file in json_list]

    # Sort Nifti and JSON file lists by acquisition time
    nii_sorted = [file for _, file in sorted(zip(acq_time, nii_list))]
    json_sorted = [file for _, file in sorted(zip(acq_time, json_list))]

    # Finally sort acquisition times
    acq_sorted = sorted(acq_time)

    return nii_sorted, json_sorted, acq_sorted


def organize_series(
        conv_dir,
        first_pass,
        prot_dict,
        src_dir,
        sid,
        ses,
        key_flags,
        nii_ext,
        do_cleanup=False,
        overwrite=False,
        auto=False):
    """
    Organize dcm2niix output in the work/ folder into BIDS

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
    :param key_flags: dict
        dictionary of flags for filename keys (echo-, part-, recon-)
    :param do_cleanup: bool
        clean up conversion directory
    :param overwrite: bool
        overwrite flag
    :param compression: bool
        Nifti compression method for dcm2niix ('n' = no compression)
    :param auto: bool
        auto build translator dictionary from dcm2niix output in work/
    :return:
    """

    # Proceed if conversion directory exists
    if os.path.isdir(conv_dir):

        # Get Nifti file list ordered by acquisition time
        nii_list, json_list, acq_times = ordered_file_list(conv_dir, nii_ext)

        # Infer run numbers accounting for duplicates.
        # Only used if run-* not present in translator BIDS filename stub
        if first_pass:
            run_no = None
        else:
            run_no = tr.auto_run_no(nii_list, prot_dict)

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        for fc, src_nii_fname in enumerate(nii_list):

            # JSON sidecar for this image
            src_json_fname = json_list[fc]

            # Parse image filename into fields
            d2n_info = bio.parse_dcm2niix_fname(src_nii_fname)

            # Check if we're creating a new protocol dictionary
            if first_pass:

                print(f"  Adding protocol {d2n_info['SerDesc']} to dictionary")

                # Add current protocol to protocol dictionary
                if auto:
                    prot_dict[d2n_info['SerDesc']] = tr.auto_translate(d2n_info, src_json_fname)
                else:
                    prot_dict[d2n_info['SerDesc']] = ["EXCLUDE_BIDS_Directory", "EXCLUDE_BIDS_Name", "UNASSIGNED"]

            else:

                # Warn if not found and continue
                if not os.path.isfile(src_json_fname):
                    print('* WARNING: JSON sidecar %s not found' % src_json_fname)
                    continue

                if d2n_info['SerDesc'] in prot_dict.keys():

                    if prot_dict[d2n_info['SerDesc']][0].startswith('EXCLUDE'):

                        # Skip excluded protocols
                        print('* Excluding protocol ' + str(d2n_info['SerDesc']))

                    else:

                        print('  Organizing ' + str(d2n_info['SerDesc']))

                        # Use protocol dictionary to determine purpose folder, BIDS filename suffix and fmap linking
                        # Note use of deepcopy to prevent corruption of prot_dict (see Issue #36 solution by @bogpetre)
                        bids_purpose, bids_suffix, bids_intendedfor = copy.deepcopy(prot_dict[d2n_info['SerDesc']])

                        # Safely add run-* key to BIDS suffix
                        bids_suffix = tr.add_run_number(bids_suffix, run_no[fc])

                        # Assume the IntendedFor field should also have a run-* key added
                        prot_dict = fmaps.add_intended_run(prot_dict, d2n_info, run_no[fc])

                        # Create BIDS purpose directory
                        bids_purpose_dir = os.path.join(src_dir, bids_purpose)
                        bio.safe_mkdir(bids_purpose_dir)

                        # Complete BIDS filenames for image and sidecar
                        if ses:
                            bids_prefix = 'sub-' + sid + '_ses-' + ses + '_'
                        else:
                            bids_prefix = 'sub-' + sid + '_'

                        # Construct BIDS Nifti and JSON filenames
                        # Issue 105: remember to account for --compress n flag with .nii extension
                        bids_nii_fname = os.path.join(bids_purpose_dir, bids_prefix + bids_suffix + nii_ext)
                        bids_json_fname = bids_nii_fname.replace(nii_ext, '.json')

                        # Add prefix and suffix to IntendedFor values
                        if 'UNASSIGNED' not in bids_intendedfor:
                            if isinstance(bids_intendedfor, str):
                                # Single linked image
                                bids_intendedfor = fmaps.build_intendedfor(sid, ses, bids_intendedfor, nii_ext)
                            else:
                                # Loop over all linked images
                                for ifc, ifstr in enumerate(bids_intendedfor):
                                    # Avoid multiple substitutions
                                    if nii_ext not in ifstr:
                                        bids_intendedfor[ifc] = fmaps.build_intendedfor(sid, ses, ifstr, nii_ext)

                        # Special handling for specific purposes (anat, func, fmap, dwi, etc)
                        # This function populates the BIDS structure with the image and adjusted sidecar
                        tr.purpose_handling(bids_purpose,
                                            bids_intendedfor,
                                            d2n_info['SeqName'],
                                            src_nii_fname,
                                            src_json_fname,
                                            bids_nii_fname,
                                            bids_json_fname,
                                            key_flags,
                                            overwrite,
                                            nii_ext)
                else:

                    # Skip protocols not in the dictionary
                    print('* Protocol ' + str(d2n_info['SerDesc']) + ' is not in the dictionary, did not convert.')

        if not first_pass:

            # Optional working directory cleanup after Pass 2
            if do_cleanup:
                print('  Cleaning up temporary files')
                shutil.rmtree(conv_dir)
            else:
                print('  Preserving conversion directory')


def handle_multiecho(work_json_fname, bids_json_fname, echo_flag, nii_ext):
    """
    Handle multiecho recons converted using dcm2niix
    As of dcm2niix v1.0.20211220 multiple echo recons have suffices:
    *_e{:d}[_ph].(nii.gz | json)
    _ph suffix handled separately (see handle_complex)

    :param work_json_fname: string
        path to JSON sidecar in working directory
    :param bids_json_fname: string
        path to JSON sidecar in output BIDS tree
    :param echo_flag: bool
        flag to add echo- key to filename (if necessary)
    """

    # Isolate echo/part suffix (e*[_ph])
    work_info = bio.parse_dcm2niix_fname(work_json_fname)
    suffix = work_info['Suffix']

    # Default BIDS Nifti filename from JSON filename
    bids_nii_fname = bids_json_fname.replace('.json', nii_ext)

    if suffix.startswith('e'):

        print('    Multiple echoes detected')

        # Split at '_' if present
        chunks = suffix.split('_')
        echo_num = int(chunks[0][1:])
        print(f'    Echo number {echo_num:d}')

        # Add an "echo-{echo_num}" key to the BIDS Nifti and JSON filenames
        if echo_flag:
            bids_nii_fname, bids_json_fname = tr.add_bids_key(bids_json_fname, 'echo', echo_num, nii_ext)

    return bids_nii_fname, bids_json_fname


def handle_complex(work_json_fname, bids_json_fname, part_flag, nii_ext):
    """
    Handle complex recons converted using dcm2niix
    As of dcm2niix v1.0.20211220 only the phase recon has a 'ph' suffix
    so check if a mag file (without suffix) has a phase partner

    :param work_json_fname: string
        path to JSON sidecar in working directory
    :param bids_json_fname: string
        path to JSON sidecar in output BIDS tree
    :param part_flag: bool
        flag to add part- key to filename (if necessary)
    """

    # Extract dcm2niix keys from filename
    work_keys = bio.parse_dcm2niix_fname(work_json_fname)
    suffix = work_keys['Suffix']

    # Extract keys and containing directory from BIDS pathname
    bids_keys, bids_dname = tr.bids_filename_to_keys(bids_json_fname)

    # Optionally add part- key to BIDS filename
    if part_flag:

        # Check for phase image first
        if suffix.endswith('ph'):
            print('    Phase image detected')
            bids_keys['part'] = 'phase'
        else:
            print('    Magnitude image detected')
            bids_keys['part'] = 'mag'

    # Modify JSON filename with complex part key
    bids_json_fname = tr.bids_keys_to_filename(bids_keys, bids_dname)

    # Construct associated BIDS Nifti filename
    bids_nii_fname = bids_json_fname.replace('.json', nii_ext)

    return bids_nii_fname, bids_json_fname


def handle_bias_recon(work_json_fname, bids_json_fname, recon_flag, nii_ext):
    """
    Handle bias correction (Siemens NORM flag)

    :param work_json_fname: string
        path to JSON sidecar in working directory
    :param bids_json_fname: string
        path to JSON sidecar in output BIDS tree
    :param recon_flag: bool
        flag to add rec- key to filename (if necessary)
    """

    # Load recon type from work JSON sidecar
    work_json = bio.read_json(work_json_fname)
    image_type = work_json['ImageType']
    recon_value = 'norm' if 'NORM' in image_type else 'bias'

    # Add a recon- key to the BIDS filename
    if recon_flag:
        bids_nii_fname, bids_json_fname = tr.add_bids_key(bids_json_fname, 'rec', recon_value, nii_ext)
    else:
        bids_nii_fname = bids_json_fname.replace('.json', nii_ext)

    return bids_nii_fname, bids_json_fname


def dcm2niix_json_fname(info, ser_no, suffix):
    """
    Construct a dcm2niix filename from parse_dcm2niix_fname dictionary
    Current dcm2niix version: v20200331
    :param info: dict
        series metadata
    :param ser_no: int
        series number
    :param suffix: str
        BIDS filename suffix
    :return: str
        dcm2niix filename
    """

    if len(suffix) > 0:
        ser_no = '{}_{}'.format(ser_no, suffix)

    # Construct dcm2niix mag1 filename
    fname = '{}--{}--{}--{}.json'.format(
        info['SubjName'],
        info['SerDesc'],
        info['SeqName'],
        ser_no)

    fname_full = os.path.join(info['DirName'], fname)

    return fname_full


def check_dcm2niix_version(min_version='v1.0.20181125'):

    output = subprocess.check_output('dcm2niix')

    # Search for version in output
    match = re.findall(b"v\d.\d.\d+", output)

    if match:

        version = match[0].decode('utf-8')
        print('\ndcm2niix version %s detected' % version)

        if version < min_version:
            print('* please update to dcm2niix version %s or later' % min_version)
            sys.exit(1)

    else:

        print('* dcm2niix version not detected')
        print('* check that dcm2niix %s or later is installed correctly' % min_version)
        sys.exit(1)
