"""
Utility functions for handling protocol series tranlsation and purpose mapping

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

import os
import sys
import json
import re
import subprocess
import numpy as np
import datetime as dt

from glob import glob
from bids.layout import parse_file_entities

from .io import (nii_to_json,
                 read_json,
                 parse_bids_fname,
                 parse_dcm2niix_fname,
                 safe_copy,
                 write_json,
                 strip_extensions,
                 create_file_if_missing)


def ordered_file_list(conv_dir):
    """
    Generated list of dcm2niix Nifti output files ordered by acquisition time

    :param conv_dir: str, working conversion directory
    :return:
    """

    # Get Nifti image list from conversion directory
    nii_list = glob(os.path.join(conv_dir, '*.nii*'))

    # Derive JSON sidecar list
    json_list = [nii_to_json(nii_file) for nii_file in nii_list]

    # Pull acquisition times for each Nifti image from JSON sidecar
    acq_time = [get_acq_time(json_file) for json_file in json_list]

    # Sort Nifti and JSON file lists by acquisition time
    nii_sorted = [file for _, file in sorted(zip(acq_time, nii_list))]
    json_sorted = [file for _, file in sorted(zip(acq_time, json_list))]

    # Finally sort acquisition times
    acq_sorted = sorted(acq_time)

    return nii_sorted, json_sorted, acq_sorted


def get_acq_time(json_file):
    """
    Extract acquisition time from JSON sidecar of Nifti file

    :param json_file: str, JSON sidecar filename
    :return: acq_time: int, integer datetime
    """

    info = read_json(json_file)

    if 'AcquisitionTime' in info:
        acq_time = info['AcquisitionTime']
    else:
        print('* AcquisitionTime not found in {}'.format(json_file))
        acq_time = "00:00:00.00"

    return acq_time


def prune_intendedfors(bids_subj_dir, fmap_only):
    """
    Prune out all "IntendedFor" entries pointing to nonexistent files from all json files in given directory tree

    :param bids_subj_dir: string
        BIDS subject directory (sub-*)
    :param fmap_only: boolean
        Only looks at json files in an fmap directory
    """

    # TODO: Switch to pybids layout

    # Traverse through all directories in bids_subj_dir
    for root, dirs, files in os.walk(bids_subj_dir):
        for name in files:

            # Only examine json files, ignore dataset_description, and only work in fmap directories if so specified
            if (os.path.splitext(name)[1] == ".json" and
                    not name == "dataset_description.json" and
                    (not fmap_only or os.path.basename(root) == "fmap")):

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


def bind_fmaps(bids_subj_dir):
    """
    Bind nearest fieldmap in time to each functional series for this subject

    :param dataset_dir: string
        BIDS root directory
    """

    print('  Subject {}'.format(os.path.basename(bids_subj_dir)))

    sess_dirs = glob(os.path.join(bids_subj_dir, 'ses-*'))

    # Session loop
    for sess_dir in sess_dirs:

        print('    Session {}'.format(os.path.basename(sess_dir)))

        # Get list of BOLD fMRI JSON sidecars
        bold_jsons = glob(os.path.join(sess_dir, 'func', '*task-*_bold.json'))

        # Get acquisition times for all BOLD and fieldmap series
        t_bold = np.array([acqtime_mins(fname) for fname in bold_jsons])

        # Get list of all SE-EPI fieldmaps
        epi_fmap_jsons = glob(os.path.join(sess_dir, 'fmap', '*_dir-*_epi.json'))

        if not epi_fmap_jsons:
            print('* No SE-EPI fieldmaps found - skipping this subject/series')
            break

        # Get list of SE-EPI directions
        dirs = []
        for fname in epi_fmap_jsons:
            ents = parse_file_entities(fname)
            if 'direction' in ents:
                dirs.append(ents['direction'])
        fmap_dirs = np.unique(dirs)

        # Loop over directions
        for fmap_dir in fmap_dirs:

            print('    Scanning for dir-{} SE-EPI fieldmaps'.format(fmap_dir))

            # New SE-EPI fmap list for this direction
            fmap_dir_jsons = glob(os.path.join(sess_dir, 'fmap', '*_dir-{}*_epi.json'.format(fmap_dir)))

            # Create list for storing IntendedFor lists
            intended_for = [ [] for ic in range(len(fmap_dir_jsons)) ]

            # Get SE-EPI fmap acquisition times
            t_epi_fmap = np.array([acqtime_mins(fname) for fname in fmap_dir_jsons])

            # Find the closest fieldmap in time to each BOLD series
            for ic, bold_json in enumerate(bold_jsons):

                # Time difference between all fieldmaps in this direction and current BOLD series
                dt = np.abs(t_bold[ic] - t_epi_fmap)

                # Index of closest fieldmap to this BOLD series
                idx = np.argmin(dt)

                # Add this BOLD series image name to list for this fmap
                intended_for[idx].append(bids_intended_name(bold_json))

            # Replace IntendedFor field in fmap JSON file
            for fc, json_fname in enumerate(fmap_dir_jsons):
                info = read_json(json_fname)
                info['IntendedFor'] = intended_for[fc]
                write_json(json_fname, info, overwrite=True)


def bids_intended_name(json_fname):

    # Replace .json with .nii.gz
    tmp1 = json_fname.replace('.json', '.nii.gz')
    base1 = os.path.basename(tmp1)

    tmp2 = os.path.dirname(tmp1)
    base2 = os.path.basename(tmp2)

    tmp3 = os.path.dirname(tmp2)
    base3 = os.path.basename(tmp3)

    return(os.path.join(base3, base2, base1))


def acqtime_mins(json_fname):

    with open(json_fname) as fd:

        info = json.load(fd)

        t1 = dt.datetime.strptime(info['AcquisitionTime'], '%H:%M:%S.%f0')
        t0 = dt.datetime(1900, 1, 1)
        t_mins = np.float((t1 - t0).total_seconds() / 60.0)

    return t_mins


def purpose_handling(bids_purpose, bids_intendedfor, seq_name,
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
    bids_info = read_json(work_json_fname)

    if bids_purpose == 'func':

        if seq_name == 'EP':

            print('    EPI detected')
            create_events_template(bids_nii_fname, overwrite)

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

        # Check for MEGE vs SE-EPI fieldmap images
        # MEGE will have a 'GR' sequence, SE-EPI will have 'EP'

        print('    Identifying fieldmap image type')

        if seq_name == 'GR':

            print('    GRE detected')
            print('    Identifying magnitude and phase images')

            # Siemens: Dual gradient echo fieldmaps reconstruct to three series
            # (Requires dcm2nixx v1.0.20180404 or later for echo number suffix)
            # *--GR--<serno>_e1.<ext> : magnitude image from echo 1
            # *--GR--<serno>_e2.<ext> : magnitude image from echo 2
            # *--GR--<serno+1>_ph.<ext> : inter-echo phase difference

            # Pull dcm2niix filename info
            work_info = parse_dcm2niix_fname(work_nii_fname)

            if 'e1' in work_info['Suffix']:

                print('    Echo 1 magnitude detected')

                # Replace existing contrast suffix (if any) with '_magnitude1'
                bids_nii_fname = replace_contrast(bids_nii_fname, 'magnitude1')
                bids_json_fname = []  # Do not copy sidecar

            elif 'e2' in work_info['Suffix']:

                print('    Echo 2 magnitude detected')

                # Replace existing contrast suffix (if any) with '_magnitude1'
                bids_nii_fname = replace_contrast(bids_nii_fname, 'magnitude2')
                bids_json_fname = []  # Do not copy sidecar

            elif 'ph' in work_info['Suffix']:

                print('    Interecho phase difference detected')

                # Replace existing contrast suffix (if any) with '_phasediff'
                bids_nii_fname = replace_contrast(bids_nii_fname, 'phasediff')
                bids_json_fname = replace_contrast(bids_json_fname, 'phasediff')

                # Extract TE1 and TE2 from mag and phase JSON sidecars
                te1, te2 = fmap_echotimes(work_json_fname)
                bids_info['EchoTime1'] = te1
                bids_info['EchoTime2'] = te2

            else:

                print('*   Magnitude or phase image not found - skipping')
                bids_nii_fname = []
                bids_json_fname = []

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
            known_subjects = {l.split('\t')[0] for l in f.readlines()}

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


def auto_run_no(file_list, prot_dict):
    """
    Search for duplicate series names in dcm2niix output file list
    Return inferred run numbers accounting for duplication and multiple recons from single acquisition

    NOTES:
    - Multiple recons generated by single acquisition (eg multiecho fieldmaps, localizers, etc) are
      handled through the dcm2niix extensions (_e1, _ph, _i00001, etc).
    - Series number resets following subject re-landmarking make the SerNo useful only for
      determining series uniqueness and not for ordering or run numbering.

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

    run_no = np.zeros(len(file_list))

    for unique_desc in unique_descs:
        run_count = 1
        for i, desc in enumerate(desc_list):
            if desc == unique_desc:
                run_no[i] = run_count
                run_count += 1

    return run_no


def build_intendedfor(sid, ses, bids_suffix):
    """
    Build the IntendedFor entry for a fieldmap sidecar

    :param: sid, str, Subject ID
    :param: ses, str,  Session number
    :param: bids_suffix
    :return: ifstr, str
    """

    bids_name = os.path.basename(bids_suffix)
    bids_type = os.path.dirname(bids_suffix)
    if bids_type == '':
        bids_type = 'func'

    # Complete BIDS filenames for image and sidecar
    if ses:
        # If sessions are being used, add session directory to IntendedFor field
        ifstr = os.path.join('ses-' + ses, bids_type, 'sub-' + sid + '_ses-' + ses + '_' + bids_name + '.nii.gz')
    else:
        ifstr = os.path.join(bids_type, 'sub-' + sid + '_' + bids_name + '.nii.gz')

    return ifstr


def add_intended_run(prot_dict, info, run_no):
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

            # Construct a list of the intended runs
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
                new_suffix = add_run_number(suffixes[idx], run_no)

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


def replace_contrast(fname, new_contrast):
    """
    Replace contrast suffix (if any) of BIDS filename

    :param fname: str, original BIDS Nifti or JSON filename
    :param new_contrast: str, replacement contrast suffix
    :return: new_fname: str, modified BIDS filename
    """

    bids_keys = parse_bids_fname(fname)

    if 'contrast' in bids_keys:
        new_fname = fname.replace(bids_keys['contrast'], new_contrast)
    else:
        fstub, fext = strip_extensions(fname)
        new_fname = fstub + '_' + new_contrast + fext

    return new_fname


def fmap_echotimes(src_phase_json_fname):
    """
    Extract TE1 and TE2 from mag and phase MEGE fieldmap pairs

    :param src_phase_json_fname: str
    :return:
    """

    # Init returned TEs
    te1, te2 = 0.0, 0.0

    if os.path.isfile(src_phase_json_fname):

        # Read phase image metadata
        phase_dict = read_json(src_phase_json_fname)

        # Populate series info dictionary from dcm2niix output filename
        info = parse_dcm2niix_fname(src_phase_json_fname)

        # Siemens: Magnitude 1 series number is one less than phasediff series number
        mag1_ser_no = str(int(info['SerNo']) - 1)

        # Construct dcm2niix mag1 JSON filename
        # Requires dicm2niix v1.0.20180404 or later for echo number suffix '_e1'
        src_mag1_json_fname = info['SubjName'] + '--' + info['SerDesc'] + '--' + \
            info['SeqName'] + '--' + mag1_ser_no + '_e1.json'
        src_mag1_json_path = os.path.join(os.path.dirname(src_phase_json_fname), src_mag1_json_fname)

        # Read mag1 metadata
        mag1_dict = read_json(src_mag1_json_path)

        # Add te1 key and rename TE2 key
        if mag1_dict:
            te1 = mag1_dict['EchoTime']
            te2 = phase_dict['EchoTime']
        else:
            print('*** Could not determine echo times multiecho fieldmap - using 0.0 ')

    else:

        print('* Fieldmap phase difference sidecar not found : ' + src_phase_json_fname)

    return te1, te2


def create_events_template(bold_fname, overwrite=False):
    """
    Create a template events file for a corresponding BOLD imaging file

    :param bold_fname: str, BOLD imaging filename (.nii.gz)
    :param overwrite: bool, Overwrite flag
    :return: Nothing
    """

    # Make specific to BOLD data to avoid overwriting with SBRef info
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


def check_dcm2niix_version(min_version='v1.0.20181125'):

    output = subprocess.check_output('dcm2niix')

    # Search for version in output
    match = re.findall(b'v\d.\d.\d+', output)

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
