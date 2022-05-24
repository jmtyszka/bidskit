"""
Utility functions for handling protocol series tranlsation and purpose mapping

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
import numpy as np

from . import fmaps
from . import dcm2niix as d2n
from .io import (read_json,
                 write_json,
                 parse_bids_fname,
                 parse_dcm2niix_fname,
                 safe_copy,
                 create_file_if_missing,
                 strip_extensions)


def purpose_handling(bids_purpose,
                     bids_intendedfor,
                     seq_name,
                     work_nii_fname,
                     work_json_fname,
                     bids_nii_fname,
                     bids_json_fname,
                     key_flags,
                     overwrite,
                     nii_ext):
    """
    Special handling for each image purpose (func, anat, fmap, dwi, etc)

    :param bids_purpose: str
        BIDS purpose directory name (eg anat, func, fmap, etc)
    :param bids_intendedfor: str
    :param seq_name: str
    :param work_nii_fname: str
        work directory dcm2niix output Nifit filename
    :param work_json_fname: str
        work directory dcm2niix output JSON filename
    :param bids_nii_fname: str
        initial BIDS filename (can be modified by this function)
    :param bids_json_fname: str
        initial BIDS JSON sidecar filename (can be modified by this function)
    :param key_flags: dict
        dictionary of filename key flags
    :param overwrite: bool
        Overwrite flag for sub-* output
    :return:
    """

    # Init DWI sidecars
    work_bval_fname = []
    work_bvec_fname = []
    bids_bval_fname = []
    bids_bvec_fname = []

    # Load the JSON sidecar
    bids_info = read_json(work_json_fname)

    if bids_purpose == 'func':

        if 'EP' in seq_name:

            print('    EPI detected')

            # Handle multiecho EPI (echo-*). Modify bids fnames as needed
            bids_nii_fname, bids_json_fname = d2n.handle_multiecho(
                work_json_fname, bids_json_fname, key_flags['Echo'], nii_ext)

            # Handle complex-valued EPI (part-*). Modify bids fnames as needed
            bids_nii_fname, bids_json_fname = d2n.handle_complex(
                work_json_fname, bids_json_fname, key_flags['Part'], nii_ext)

            # Handle task info
            create_events_template(bids_nii_fname, overwrite, nii_ext)

            # Add taskname to BIDS JSON sidecar
            bids_keys = parse_bids_fname(bids_nii_fname)
            if 'task' in bids_keys:
                bids_info['TaskName'] = bids_keys['task']
            else:
                bids_info['TaskName'] = 'unknown'

    elif bids_purpose == 'fmap':

        # Add IntendedFor field if requested through protocol translator
        if 'UNASSIGNED' not in bids_intendedfor:
            bids_info['IntendedFor'] = bids_intendedfor

        # Check for GRE vs SE-EPI fieldmap images
        # GRE will have a 'GR' sequence, SE-EPI will have 'EP'

        print('    Identifying fieldmap image type')

        if seq_name == 'GR':

            print('    Gradient echo fieldmap detected')
            print('    Identifying magnitude and phase images')

            # Update BIDS filenames according to BIDS Fieldmap Case (1 or 2 - see specification)
            bids_nii_fname, bids_json_fname = fmaps.handle_fmap_case(work_json_fname, bids_nii_fname, bids_json_fname)

        elif seq_name == 'EP':

            print('    EPI fieldmap detected')

        else:

            print('    Unrecognized fieldmap detected')
            print('    Simply copying image and sidecar to fmap directory')

    elif bids_purpose == 'anat':

        if seq_name == 'GR_IR':

            print('    IR-prepared GRE detected - likely T1w MPRAGE or MEMPRAGE')

            # Handle multiecho EPI (echo-*). Modify bids fnames as needed
            bids_nii_fname, bids_json_fname = d2n.handle_multiecho(
                work_json_fname, bids_json_fname, key_flags['Echo'], nii_ext)

            # Handle complex-valued EPI (part-*). Modify bids fnames as needed
            bids_nii_fname, bids_json_fname = d2n.handle_complex(
                work_json_fname, bids_json_fname, key_flags['Part'], nii_ext)

            # Handle biased and unbiased (NORM) reconstructions
            bids_nii_fname, bids_json_fname = d2n.handle_bias_recon(
                work_json_fname, bids_json_fname, key_flags['Recon'], nii_ext)

        elif seq_name == 'SE':

            print('    Spin echo detected - likely T1w or T2w anatomic image')
            bids_nii_fname, bids_json_fname = d2n.handle_bias_recon(
                work_json_fname, bids_json_fname, key_flags['Recon'], nii_ext)

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
        write_json(bids_json_fname, bids_info, overwrite)

    if bids_bval_fname:
        safe_copy(work_bval_fname, bids_bval_fname, overwrite)

    if bids_bvec_fname:
        safe_copy(work_bvec_fname, bids_bvec_fname, overwrite)


def add_participant_record(studydir, subject, age, sex):
    """
    Copied from heudiconv, this solution is good b/c it checks if the same subject ID already exists
    :param studydir:
    :param subject:
    :param age:
    :param sex:
    :return:
    """

    participants_tsv = os.path.join(studydir, 'participants.tsv')
    participant_id = 'sub-%s' % subject

    if not create_file_if_missing(participants_tsv, '\t'.join(['participant_id', 'age', 'sex', 'group']) + '\n'):

        # Check if subject record already exists
        with open(participants_tsv) as f:
            f.readline()
            known_subjects = {this_line.split('\t')[0] for this_line in f.readlines()}

        if participant_id in known_subjects:
            return

    # Add a new participant
    with open(participants_tsv, 'a') as f:
        f.write(
            '\t'.join(map(str, [participant_id, age.lstrip('0').rstrip('Y') if age else 'N/A', sex, 'control'])) + '\n')


def add_run_number(bids_suffix, run_no):
    """
    Safely add run number to BIDS suffix
    Handle prior existence of run-* in BIDS filename template from protocol translator

    :param bids_suffix, str
    :param run_no, int
    :return: new_bids_suffix, str
    """

    if "run-" in bids_suffix:

        # Preserve existing run-%d value in suffix
        print('  * BIDS suffix already contains run number - skipping')
        new_bids_suffix = bids_suffix

    else:

        if '_' in bids_suffix:

            # Add '_run-x' before final suffix
            bmain, bseq = bids_suffix.rsplit('_', 1)
            new_bids_suffix = f"{bmain:s}_run-{run_no:d}_{bseq:s}"

        else:

            # Isolated final suffix - just add 'run-%d_' as a prefix
            new_bids_suffix = f"run-{run_no:d}_{bids_suffix:s}"

    return new_bids_suffix


def add_bids_key(bids_json_fname, key_name, key_value, nii_ext):
    """
    Add a new key to a BIDS filename
    If this key is already present, print warning and don't replace key
    """

    # Extract key values from BIDS filename
    keys, dname = bids_filename_to_keys(bids_json_fname)

    if key_name in keys:

        print(f'  * Key {key_name} already present in filename - skipping')
        new_bids_json_fname = bids_json_fname

    else:

        # Add new key to dictionary
        keys[key_name] = key_value

        # Init new filename with containing path
        new_bids_json_fname = bids_keys_to_filename(keys, dname)

    # Construct associated Nifti filename
    new_bids_nii_fname = new_bids_json_fname.replace('.json', nii_ext)

    return new_bids_nii_fname, new_bids_json_fname


def bids_filename_to_keys(bids_fname):
    """
    Extract BIDS key values from filename
    Substitute short key names for long names used by parse_file_entities()
    """

    # Parse BIDS filename with internal function that supports part- key
    keys, dname = parse_bids_fname(bids_fname)

    # Substitute short key names
    if 'subject' in keys:
        keys['sub'] = keys.pop('subject')
    if 'session' in keys:
        keys['ses'] = keys.pop('session')
    if 'acquisition' in keys:
        keys['acq'] = keys.pop('acquisition')

    return keys, dname


def bids_keys_to_filename(keys, dname):
    """
    Construct BIDS filename from keys
    - key dictionary must include suffix and extension
    """

    # Correct key order from BIDS spec
    key_order = ['sub', 'ses', 'task', 'acq', 'dir', 'rec', 'run', 'echo', 'part']

    # Init with the containing directory and trailing file separator if dname provided
    if dname:
        bids_fname = dname + os.path.sep
    else:
        bids_fname = ''

    # Construct BIDS filename from keys in correct order
    for key in key_order:
        if key in keys:
            bids_fname += f"{key}-{keys[key]}_"

    # Add final pulse sequence suffix and extension
    if 'suffix' in keys:
        bids_fname += keys['suffix']

    if 'extension' in keys:
        bids_fname += keys['extension']

    return bids_fname


def bids_legalize_keys(keys):
    """
    Scrub illegal characters from BIDS keys
    """

    bad_chars = ['-', '_']

    for key in keys:
        value = keys[key]
        for bc in bad_chars:
            value = value.replace(bc, '')
        keys[key] = value

    return keys


def auto_run_no(file_list, prot_dict):
    """
    Search for duplicate series names in dcm2niix output file list
    Return inferred run numbers accounting for duplication and multiple recons from single acquisition
    NOTES:
    - Multiple recons generated by single acquisition (eg multiecho fieldmaps, localizers, etc) are
      handled through the dcm2niix extensions (_e1, e2_ph, _i00001, etc).
    - Series number resets following subject re-landmarking make the SerNo useful only for
      determining series uniqueness and not for ordering or run numbering.
    Current dcm2niix version: v20200331
    :param file_list: list of str
        Nifti file name list
    :param prot_dict: dictionary
        Protocol translation dictionary
    :return: run_num, array of int
    """

    # Construct list of series descriptions and original numbers from file names
    desc_list = []

    for fname in file_list:

        # Parse dcm2niix filename into relevant keys, including suffix
        info = parse_dcm2niix_fname(fname)

        ser_desc = info['SerDesc']

        if ser_desc in prot_dict:
            _, bids_suffix, _ = prot_dict[info['SerDesc']]
        else:
            print('')
            print('* Series description {} missing from code/Protocol_Translator.json'.format(ser_desc))
            print('* Please use EXCLUDE_BIDS_Directory and EXCLUDE_BIDS_Name instead of deleting a series entry')
            print('* Exiting')
            sys.exit(1)

        # Construct a unique series description using multirecon suffix
        ser_suffix = bids_suffix + '_' + info['Suffix']

        # Add to list
        desc_list.append(ser_suffix)

    # Find unique ser_desc entries using sets
    unique_descs = set(desc_list)

    run_no = np.zeros(len(file_list)).astype(int)

    for unique_desc in unique_descs:
        run_count = 1
        for i, desc in enumerate(desc_list):
            if desc == unique_desc:
                run_no[i] = run_count
                run_count += 1

    return run_no


def replace_contrast(fname, new_contrast):
    """
    Replace contrast suffix (if any) of BIDS filename
    :param fname: str, original BIDS Nifti or JSON filename
    :param new_contrast: str, replacement contrast suffix
    :return: new_fname: str, modified BIDS filename
    """

    bids_keys = parse_bids_fname(fname)

    if 'suffix' in bids_keys:
        new_fname = fname.replace(bids_keys['suffix'], new_contrast)
    else:
        fstub, fext = strip_extensions(fname)
        new_fname = fstub + '_' + new_contrast + fext

    return new_fname


def create_events_template(bold_fname, overwrite, nii_ext):
    """
    Create a template events file for a corresponding BOLD imaging file
    :param bold_fname: str
        BOLD imaging filename
    :param overwrite: bool
        Overwrite flag
    :param nii_ext: str
        Nifti image extension accounting for compression (*.nii or *.nii.gz)
    """

    # Make specific to BOLD data to avoid overwriting with SBRef info
    if "_bold" + nii_ext in bold_fname:

        # Remove echo, part keys from filename. Only one events file required for each task/acq
        keys, dname = bids_filename_to_keys(bold_fname)
        if 'echo' in keys:
            del keys['echo']
        if 'part' in keys:
            del keys['part']
        bold_fname = bids_keys_to_filename(keys, dname)

        events_fname = bold_fname.replace("_bold" + nii_ext, "_events.tsv")
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


def auto_translate(info, json_fname):
    """
    Construct protocol translator from original series descriptions
    - assumes series descriptions are ReproIn-style
    """

    ser_desc = info['SerDesc']

    # List of possible suffices for each BIDS type directory
    bids_types = {
        'func': ['bold', 'sbref'],
        'anat': ['T1w', 'T2w', 'PDw', 'T2starw', 'FLAIR',
                 'defacemask', 'MEGRE', 'MESE', 'VFA', 'IRT1',
                 'MP2RAGE', 'MPM', 'MTS', 'MTR'],
        'fmap': ['epi'],
        'dwi': ['dwi']
    }

    # Use BIDS filename parser on ReproIn-style series description
    # Returns any BIDS-like key values from series description string
    # The closer the series descriptions are to Repro-In specs, the
    # better this works.
    bids_keys, _ = parse_bids_fname(ser_desc)

    # Infer BIDS type directory
    bids_dir = 'anat'
    for bids_type in bids_types:
        if bids_keys['suffix'] in bids_types[bids_type]:
            bids_dir = bids_type

    # Scrub any illegal characters from BIDS key values (eg "-_.")
    bids_keys = bids_legalize_keys(bids_keys)

    # Reconstitute bids filename stub template from identified BIDS keys
    bids_stub = bids_keys_to_filename(bids_keys, '')

    # Always set IntendedFor to unassigned at this stage.
    # Filled automatically if requested during translation
    bids_intendedfor = 'UNASSIGNED'

    print('')
    print(f'Series Description : {ser_desc}')
    print(f'BIDS directory     : {bids_dir}')
    print(f'BIDS stub          : {bids_stub}')
    print(f'BIDS IntendedFor   : {bids_intendedfor}')

    return [bids_dir, bids_stub, bids_intendedfor]