"""
Main function organizing dcm2niix output into BIDS subject/session directories

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
import shutil
from . import translate as btr
from . import io as bio
import copy


def organize_series(conv_dir, first_pass, prot_dict, src_dir, sid, ses, clean_conv_dir, overwrite=False):
    """
    Organize dcm2niix output into BIDS subject/session directory

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
    :param clean_conv_dir: bool
        clean up conversion directory
    :param overwrite: bool
        overwrite flag
    :return:
    """

    # Flag for working conversion directory cleanup
    do_cleanup = clean_conv_dir

    # Proceed if conversion directory exists
    if os.path.isdir(conv_dir):

        # Get Nifti file list ordered by acquisition time
        nii_list, json_list, acq_times = btr.ordered_file_list(conv_dir)

        # Infer run numbers accounting for duplicates.
        # Only used if run-* not present in translator BIDS filename stub
        if not first_pass:
            run_no = btr.auto_run_no(nii_list, prot_dict)

        # Loop over all Nifti files (*.nii, *.nii.gz) for this subject
        for fc, src_nii_fname in enumerate(nii_list):

            # Parse image filename into fields
            info = bio.parse_dcm2niix_fname(src_nii_fname)

            # Check if we're creating new protocol dictionary
            if first_pass:

                print('  Adding protocol %s to dictionary template' % info['SerDesc'])

                # Add current protocol to protocol dictionary
                # Use default EXCLUDE_* values which can be changed (or not) by the user
                prot_dict[info['SerDesc']] = ["EXCLUDE_BIDS_Directory", "EXCLUDE_BIDS_Name", "UNASSIGNED"]

            else:

                # JSON sidecar for this image
                src_json_fname = json_list[fc]

                # Warn if not found and continue
                if not os.path.isfile(src_json_fname):
                    print('* WARNING: JSON sidecar %s not found' % src_json_fname)
                    continue

                if info['SerDesc'] in prot_dict.keys():

                    if prot_dict[info['SerDesc']][0].startswith('EXCLUDE'):

                        # Skip excluded protocols
                        print('* Excluding protocol ' + str(info['SerDesc']))

                    else:

                        print('  Organizing ' + str(info['SerDesc']))

                        # Use protocol dictionary to determine purpose folder, BIDS filename suffix and fmap linking
                        # Note use of deepcopy to prevent corruption of prot_dict (see Issue #36 solution by @bogpetre)
                        # TODO: Check variety of use cases for stability
                        bids_purpose, bids_suffix, bids_intendedfor = copy.deepcopy(prot_dict[info['SerDesc']])

                        # Safely add run-* key to BIDS suffix
                        bids_suffix = btr.add_run_number(bids_suffix, run_no[fc])

                        # Assume the IntendedFor field should aslo have a run- added
                        prot_dict = btr.add_intended_run(prot_dict, info, run_no[fc])

                        # Create BIDS purpose directory
                        bids_purpose_dir = os.path.join(src_dir, bids_purpose)
                        bio.safe_mkdir(bids_purpose_dir)

                        # Complete BIDS filenames for image and sidecar
                        if ses:
                            bids_prefix = 'sub-' + sid + '_ses-' + ses + '_'
                        else:
                            bids_prefix = 'sub-' + sid + '_'

                        # Construct BIDS source Nifti and JSON filenames
                        bids_nii_fname = os.path.join(bids_purpose_dir, bids_prefix + bids_suffix + '.nii.gz')
                        bids_json_fname = bids_nii_fname.replace('.nii.gz', '.json')

                        # Add prefix and suffix to IntendedFor values
                        if 'UNASSIGNED' not in bids_intendedfor:
                            if isinstance(bids_intendedfor, str):
                                # Single linked image
                                bids_intendedfor = btr.build_intendedfor(sid, ses, bids_intendedfor)
                            else:
                                # Loop over all linked images
                                for ifc, ifstr in enumerate(bids_intendedfor):
                                    # Avoid multiple substitutions
                                    if '.nii.gz' not in ifstr:
                                        bids_intendedfor[ifc] = btr.build_intendedfor(sid, ses, ifstr)

                        # Special handling for specific purposes (anat, func, fmap, etc)
                        # This function populates BIDS structure with the image and adjusted sidecar
                        btr.purpose_handling(bids_purpose, bids_intendedfor, info['SeqName'],
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
