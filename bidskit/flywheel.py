"""
Flywheel tarball support functions

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
import os.path as op
from glob import glob
import subprocess
import shutil


def unpack(dataset_dir):

    src_dir = op.join(dataset_dir, 'sourcedata')
    os.makedirs(src_dir, exist_ok=True)

    # Look for one or more flywheel tarballs in the BIDS dataset root folder
    fw_tarball_list = sorted(glob(op.join(dataset_dir, 'flywheel_*.tar')))

    if len(fw_tarball_list) < 1:
        print(f'* No Flywheel DICOM tarballs found in {dataset_dir} - exiting')
    else:

        for tb_fname in fw_tarball_list:

            # Untar tarball silently
            print(f'  Unpacking {tb_fname} to {src_dir}')
            subprocess.run(['tar', 'xf', tb_fname, '-C', src_dir])

            # bidskit uses sourcedata/<SUBJECT>/<SESSION> organization
            # Flywheel uses sourcedata/<FWDIRNAME>/<GROUP>/<PROJECT>/<SUBJECT>/SESSION>
            # so move <SUBJECT> folder up three levels within sourcedata and
            # delete sourcedata/<FWDIRNAME> folder tree
            # Currently FWDIRNAME can be either 'flywheel' for web downloads or 'scitran'
            # for CLI downloads

            # Check for existence of sourcedata/flywheel or sourcedata/scitran folders
            # following untarring
            fw_web_dir = op.join(src_dir, 'flywheel')
            fw_cli_dir = op.join(src_dir, 'scitran')
            if op.isdir(fw_web_dir):
                fw_dir = fw_web_dir
            elif op.isdir(fw_cli_dir):
                fw_dir = fw_cli_dir
            else:
                raise Exception(f'Neither sourcedata/flywheel or sourcedata/scitran exist following tar extraction')

            # Assume only one group/project present in sourcedata following tarball unpacking
            subj_dir_list = sorted(glob(op.join(fw_dir, '*', '*', '*')))
            for subj_dir in subj_dir_list:
                print(f'  Moving {subj_dir} to {src_dir}')
                try:
                    shutil.move(subj_dir, src_dir)
                except shutil.Error:
                    print(f'* Subject folder already exists - skipping')
            print(f'  Deleting {fw_dir}')
            shutil.rmtree(fw_dir)

            # Unzip all session .zip files in place
            zip_list = sorted(glob(op.join(src_dir, '*', '*', '*', '*.zip')))
            for zip_fname in zip_list:
                # Unzip silently into the containing folder of the zip file
                print(f'  Unzipping {zip_fname}')
                subprocess.run(['unzip', '-qq', zip_fname, '-d', op.dirname(zip_fname)])
                # Delete the zip file
                print(f'  Deleting {zip_fname}')
                os.remove(zip_fname)
