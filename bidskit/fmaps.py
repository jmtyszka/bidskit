"""
Support functions for BIDS MRI fieldmap handling

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
import json
import bids
import numpy as np
from glob import glob

from . import io as bio
from . import dcm2niix as d2n
from . import translate as tr
from .json import (acqtime_mins)


def bind_fmaps(bids_subj_dir, no_sessions, nii_ext):
    """
    Bind nearest fieldmap in time to each functional series for this subject
    - allow only SE-EPI pair or GRE fieldmap bindings, not a mixture of both
    - if both SE-EPI and GRE fmaps are present in fmap/ IGNORE the GRE fieldmaps
    - handles no-sessions flag

    :param bids_subj_dir: string
        BIDS root directory
    :param no_sessions: bool
        Flag for session-less operation
    """

    print('  Subject {}'.format(os.path.basename(bids_subj_dir)))

    if no_sessions:
        subjsess_dirs = [bids_subj_dir]
    else:
        subjsess_dirs = sorted(glob(os.path.join(bids_subj_dir, 'ses-*')))

    # Subject/session loop
    for subjsess_dir in subjsess_dirs:

        print('    Subject/Session {}'.format(os.path.basename(subjsess_dir)))

        # Get list of BOLD fMRI JSON sidecars and acquisition times
        bold_jsons = sorted(glob(os.path.join(subjsess_dir, 'func', '*task-*_bold.json')))
        t_bold = np.array([acqtime_mins(fname) for fname in bold_jsons])

        # Find SE-EPI and GRE fieldmaps in session fmap/ folder
        fmap_dir = os.path.join(subjsess_dir, 'fmap')
        epi_fmap_jsons = sorted(glob(os.path.join(fmap_dir, '*_dir-*_epi.json')))
        gre_fmap_jsons = sorted(glob(os.path.join(fmap_dir, '*_phasediff.json')))

        if epi_fmap_jsons:
            bind_epi_fmaps(epi_fmap_jsons, bold_jsons, t_bold, no_sessions, nii_ext)
        elif gre_fmap_jsons:
            bind_gre_fmaps(gre_fmap_jsons, bold_jsons, t_bold, no_sessions, nii_ext)
        else:
            print("    * No fieldmaps detected in fmap/ - skipping")


def bind_epi_fmaps(epi_fmap_jsons, bold_jsons, t_bold, no_sessions, nii_ext):
    """
    SE-EPI fieldmap binding

    :param epi_fmap_jsons: list
    :param bold_jsons: list
    :param t_bold:
    :param no_sessions: bool
    :return:
    """

    # Get list of SE-EPI directions
    dirs = []
    for fname in epi_fmap_jsons:
        ents = bids.layout.parse_file_entities(fname)
        if 'direction' in ents:
            dirs.append(ents['direction'])
    pedirs = np.unique(dirs)

    # Loop over phase encoding directions
    for pedir in pedirs:

        print('    Scanning for dir-{} SE-EPI fieldmaps'.format(pedir))

        # List of JSONS with current PE direction
        pedir_jsons = [fname for fname in epi_fmap_jsons if pedir in fname]

        # Create list for storing IntendedFor lists
        intended_for = [[] for ic in range(len(pedir_jsons))]

        # Get SE-EPI fmap acquisition times
        t_epi_fmap = np.array([acqtime_mins(fname) for fname in pedir_jsons])

        # Find the closest fieldmap in time to each BOLD series
        for ic, bold_json in enumerate(bold_jsons):

            # Time difference between all fieldmaps in this direction and current BOLD series
            dt = np.abs(t_bold[ic] - t_epi_fmap)

            # Index of closest fieldmap to this BOLD series
            idx = np.argmin(dt)

            # Add this BOLD series image name to list for this fmap
            intended_for[idx].append(bids_intended_name(bold_json, no_sessions, nii_ext))

        # Replace IntendedFor field in fmap JSON file
        for fc, json_fname in enumerate(pedir_jsons):
            info = bio.read_json(json_fname)
            info['IntendedFor'] = intended_for[fc]
            bio.write_json(json_fname, info, overwrite=True)


def bind_gre_fmaps(gre_fmap_jsons, bold_jsons, t_bold, no_sessions):
    """
    GRE fieldmap binding

    :param gre_fmap_jsons:
    :param bold_jsons:
    :param t_bold:
    :param no_sessions: bool
    :return:
    """

    # Create list for storing IntendedFor lists
    intended_for = [[] for ic in range(len(gre_fmap_jsons))]

    # Get SE-EPI fmap acquisition times
    t_epi_fmap = np.array([acqtime_mins(fname) for fname in gre_fmap_jsons])

    # Find the closest fieldmap in time to each BOLD series
    for ic, bold_json in enumerate(bold_jsons):

        # Time difference between all fieldmaps in this direction and current BOLD series
        dt = np.abs(t_bold[ic] - t_epi_fmap)

        # Index of closest fieldmap to this BOLD series
        idx = np.argmin(dt)

        # Add this BOLD series image name to list for this fmap
        intended_for[idx].append(bids_intended_name(bold_json, no_sessions))

    # Replace IntendedFor field in fmap JSON file
    for fc, json_fname in enumerate(gre_fmap_jsons):
        info = bio.read_json(json_fname)
        info['IntendedFor'] = intended_for[fc]
        bio.write_json(json_fname, info, overwrite=True)


def bids_intended_name(json_fname, no_sessions, nii_ext):

    # Replace .json with Nifti extension ('nii.gz' or '.nii')
    nii_fname = json_fname.replace('.json', nii_ext)

    # Get intended Nifti basename from full JSON path
    nii_bname = os.path.basename(nii_fname)

    # Get type directory name ('func', 'fmap', etc)
    typedir_path = os.path.dirname(nii_fname)
    type_dname = os.path.basename(typedir_path)

    if no_sessions:

        # IntendedFor field includes type directory and image basename
        intended_path = os.path.join(type_dname, nii_bname)

    else:

        # Get session directory name (eg 'ses-1')
        sesdir_path = os.path.dirname(typedir_path)
        sesdir_dname = os.path.basename(sesdir_path)

        # IntendedFor field includes session directory, type directory and image basename
        intended_path = os.path.join(sesdir_dname, type_dname, nii_bname)

    return intended_path


def prune_intendedfors(bids_subj_dir, fmap_only):
    """
    Prune out all "IntendedFor" entries pointing to nonexistent files from all json files in given directory tree

    :param bids_subj_dir: string
        BIDS subject directory (sub-*)
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


def handle_fmap_case(work_json_fname, bids_nii_fname, bids_json_fname):
    """
    There are two popular GRE fieldmap organizations: Case 1 and Case 2
    Source: BIDS 1.4.0 Specification https://bids-specification.readthedocs.io
    Case 1
    sub-<label>/[ses-<label>/]
        fmap/
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phasediff.nii[.gz]
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phasediff.json
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude1.nii[.gz]
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude2.nii[.gz]
    Case 2
    sub-<label>/[ses-<label>/]
        fmap/
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phase1.nii[.gz]
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phase1.json
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phase2.nii[.gz]
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_phase2.json
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude1.nii[.gz]
            sub-<label>[_ses-<label>][_acq-<label>][_run-<index>]_magnitude2.nii[.gz]
    Current dcm2niix output suffices
    Current version at time of coding: v1.0.20200331
    ---
    Keep checking that this is true with later releases
    *--GR--<serno>_e1.<ext> : echo 1 magnitude image [Cases 1 and 2]
    *--GR--<serno>_e2.<ext> : echo 2 magnitude image [Cases 1 and 2]
    *--GR--<serno+1>_e1_ph.<ext> : echo 1 phase image [Case 2]
    *--GR--<serno+1>_e2_ph.<ext> : interecho phase difference [Case 1] or
                                   echo 2 phase image [Case 2]
    """

    # Pull dcm2niix filename info
    work_info = bio.parse_dcm2niix_fname(work_json_fname)
    ser_no = np.int(work_info['SerNo'])
    suffix = work_info['Suffix']

    # Base series number for magnitude images (see above)
    if suffix == 'e1' or suffix == 'e2':
        is_mag = True
        echo_no = np.int(suffix[1])
        base_ser_no = ser_no
    elif suffix == 'e1_ph' or suffix == 'e2_ph':
        is_mag = False
        echo_no = np.int(suffix[1])
        base_ser_no = ser_no - 1
    else:
        is_mag = False
        echo_no = None
        base_ser_no = None

    if base_ser_no:

        # Construct candidate JSON sidecar filenames for e1 and e2, mag and phase
        e1m_fname = d2n.dcm2niix_json_fname(work_info, base_ser_no, 'e1')
        # e2m_fname = dcm2niix_json_fname(work_info, base_ser_no, 'e2') # Optional
        e1p_fname = d2n.dcm2niix_json_fname(work_info, base_ser_no + 1, 'e1_ph')
        e2p_fname = d2n.dcm2niix_json_fname(work_info, base_ser_no + 1, 'e2_ph')

        # Check case based on existence of phase images
        fmap_case = None
        if os.path.isfile(e2p_fname):
            if os.path.isfile(e1p_fname):
                print('    Detected GRE Fieldmap Case 2')
                fmap_case = 2
            else:
                print('    Detected GRE Fieldmap Case 1')
                fmap_case = 1
        else:
            print('* GRE Fieldmap Echo 2 image missing - skipping')

        # Update BIDS nii and json filenames
        if is_mag:

            bids_nii_fname = tr.replace_contrast(bids_nii_fname, 'magnitude{}'.format(echo_no))
            bids_json_fname = tr.replace_contrast(bids_json_fname, 'magnitude{}'.format(echo_no))

        else:

            if fmap_case == 1:

                bids_nii_fname = tr.replace_contrast(bids_nii_fname, 'phasediff')
                bids_json_fname = tr.replace_contrast(bids_json_fname, 'phasediff')

                # Load echo 1 and echo 2 metadata
                e1m_info = bio.read_json(e1m_fname)
                e2p_info = bio.read_json(e2p_fname)

                # Add new fields to echo 2 phase metadata
                te1 = e1m_info['EchoTime']
                te2 = e2p_info['EchoTime']

                print(f'      GRE TE1 : {te1:0.5f} ms')
                print(f'      GRE TE2 : {te2:0.5f} ms')
                print(f'      GRE dTE : {(te2-te1):0.5f} ms')

                e2p_info['EchoTime1'] = te1
                e2p_info['EchoTime2'] = te2

                # Re-write echo 2 phase JSON sidecar
                print('    Updating Echo 2 Phase JSON sidecar')
                bio.write_json(e2p_fname, e2p_info, overwrite=True)

            else:

                bids_nii_fname = tr.replace_contrast(bids_nii_fname, 'phase{}'.format(echo_no))
                bids_json_fname = tr.replace_contrast(bids_json_fname, 'phase{}'.format(echo_no))

    else:

        print('* Could not find echo 1 and 2 images for GRE Fieldmap - skipping')

    return bids_nii_fname, bids_json_fname


def build_intendedfor(sid, ses, bids_suffix, nii_ext):
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
        ifstr = os.path.join('ses-' + ses, bids_type, 'sub-' + sid + '_ses-' + ses + '_' + bids_name + nii_ext)
    else:
        ifstr = os.path.join(bids_type, 'sub-' + sid + '_' + bids_name + nii_ext)

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
                new_suffix = tr.add_run_number(suffixes[idx], run_no)

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
