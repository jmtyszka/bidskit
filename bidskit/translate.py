"""
Utility functions for handling protocol series tranlsation and purpose mapping
"""

import os
import json
import bidskit.io as bio
import numpy as np


def prune_intendedfors(bids_subj_dir, fmap_only):
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
    info = bio.read_json(work_json_fname)

    if bids_purpose == 'func':

        if seq_name == 'EP':

            print('    EPI detected')
            bio.events_template(bids_nii_fname, overwrite)

            # Add taskname to BIDS JSON sidecar
            bids_keys = bio.parse_bids_fname(bids_nii_fname)
            if 'task' in bids_keys:
                info['TaskName'] = bids_keys['task']
            else:
                info['TaskName'] = 'unknown'

    elif bids_purpose == 'fmap':

        # Add IntendedFor field if requested through protocol translator
        if 'UNASSIGNED' not in bids_intendedfor:
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
                        te1, te2 = fmap_echotimes(work_json_fname)
                        info['EchoTime1'] = te1
                        info['EchoTime2'] = te2

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
        bio.safe_copy(work_nii_fname, str(bids_nii_fname), overwrite)

    if bids_json_fname:
        bio.write_json(bids_json_fname, info, overwrite)

    if bids_bval_fname:
        bio.safe_copy(work_bval_fname, bids_bval_fname, overwrite)

    if bids_bvec_fname:
        bio.safe_copy(work_bvec_fname, bids_bvec_fname, overwrite)


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

    if not bio.create_file_if_missing(participants_tsv, '\t'.join(['participant_id', 'age', 'sex', 'group']) + '\n'):

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


def auto_run_no(file_list):
    """
    Search for duplicate series names in dcm2niix output file list
    Return inferred run numbers accounting for duplication

    :param file_list: list of str
    :return: run_num, array of int
    """

    # Construct list of series descriptions and original numbers from file names
    ser_desc_list = []
    for fname in file_list:
        info = bio.parse_dcm2niix_fname(fname)
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
        phase_dict = bio.read_json(src_phase_json_fname)

        # Populate series info dictionary from dcm2niix output filename
        info = bio.parse_dcm2niix_fname(src_phase_json_fname)

        # Magnitude 1 series number is one less than phasediff series number
        mag1_ser_no = str(int(info['SerNo']) - 1)

        # Construct dcm2niix mag1 JSON filename
        # Requires dicm2niix v1.0.20180404 or later for echo number suffix '_e1'
        src_mag1_json_fname = info['SubjName'] + '--' + info['SerDesc'] + '--' + \
            info['SeqName'] + '--' + mag1_ser_no + '_e1.json'
        src_mag1_json_path = os.path.join(os.path.dirname(src_phase_json_fname), src_mag1_json_fname)

        # Read mag1 metadata
        mag1_dict = bio.read_json(src_mag1_json_path)

        # Add te1 key and rename TE2 key
        if mag1_dict:
            te1 = mag1_dict['EchoTime']
            te2 = phase_dict['EchoTime']
        else:
            print('*** Could not determine echo times multiecho fieldmap - using 0.0 ')

    else:

        print('* Fieldmap phase difference sidecar not found : ' + src_phase_json_fname)

    return te1, te2
