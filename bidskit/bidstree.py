"""
Class for creating and managing BIDS directory tree and essential files

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
import json
import subprocess
import pkg_resources
import shutil

from . import io as bio


class BIDSTree:

    def __init__(self, dataset_dir, overwrite=False):

        print('Initializing BIDS dataset directory tree in %s' % dataset_dir)

        self.bids_dir = dataset_dir
        self.sourcedata_dir = os.path.join(dataset_dir, 'sourcedata')
        self.derivatives_dir = os.path.join(dataset_dir, 'derivatives')
        self.code_dir = os.path.join(dataset_dir, 'code')
        self.work_dir = os.path.join(dataset_dir, 'work', 'bidskit')

        # sourcedata should already exist - no need to create
        # Existence check in __main__

        # Create required directories
        # Note: sourcedata/ must already be present and filled with DICOM images
        bio.safe_mkdir(self.derivatives_dir)
        bio.safe_mkdir(self.code_dir)
        bio.safe_mkdir(self.work_dir)

        # code/Protocol_Translator.json file path
        self.translator_file = os.path.join(self.code_dir, 'Protocol_Translator.json')

        print('Creating file templates required for BIDS compliance')

        # Copy BIDS-compliant JSON templates to BIDS directory root
        self.copy_template('README.md', 'README.md')
        self.copy_template('CHANGES', 'CHANGES')
        self.copy_template('dataset_description.json', 'dataset_description.json')
        self.copy_template('participants.json', 'participants.json')
        self.copy_template('bidsignore', '.bidsignore')

    def write_translator(self, translator):
        """
        Write protocol translation dictionary template to JSON file

        :param translator: dictionary, translation dictionary to write
        :return: None
        """

        if os.path.isfile(self.translator_file):

            print('* Protocol dictionary already exists : ' + self.translator_file)
            print('* Skipping creation of new dictionary')

        else:

            json_fd = open(self.translator_file, 'w')
            json.dump(translator, json_fd, indent=4, separators=(',', ':'))
            json_fd.close()

            print('')
            print('---')
            print('New protocol dictionary created : %s' % self.translator_file)
            print('Remember to replace "EXCLUDE" values in dictionary with an appropriate image description')
            print('For example "MP-RAGE T1w 3D structural" or "MB-EPI BOLD resting-state"')
            print('---')
            print('')

        return

    def read_translator(self):
        """
        Read protocol translations from JSON file in DICOM directory

        :return: translator: dictionary
        """

        if os.path.isfile(self.translator_file):

            # Read JSON protocol translator
            json_fd = open(self.translator_file, 'r')
            translator = json.load(json_fd)
            json_fd.close()

        else:

            translator = dict()

        return translator

    def validate(self):
        """
        Run BIDS tree through the command line BIDS validator

        :return:
        """

        # Check for bids-validator installation
        try:
            cmd = ['bids-validator', self.bids_dir, '-v']
            subprocess.check_output(cmd)
        except FileNotFoundError:
            print('')
            print('* Optional external bids-validator not found')
            print('* Please see https://github.com/jmtyszka/bidskit/blob/master/docs/Installation.md')
            print('* for more information')
            sys.exit(0)

        print('\n----------------------')
        print('Running BIDS validator')
        print('----------------------\n')

        # Run bids-validator on BIDS dataset
        subprocess.run(['bids-validator', self.bids_dir])

    def copy_template(self, tpl_fname, dest_fname):
        """
        Copy standard BIDS top-level templates to BIDS root directory
        """

        tpl_pname = pkg_resources.resource_filename(
            __name__,
            os.path.join('templates', tpl_fname)
        )
        out_pname = os.path.join(self.bids_dir, dest_fname)

        print(f'Copying {tpl_pname} to {out_pname}')

        try:
            shutil.copyfile(tpl_pname, out_pname)
        except FileNotFoundError:
            print('* {tpl_pname} not found - check installation folder permissions')
