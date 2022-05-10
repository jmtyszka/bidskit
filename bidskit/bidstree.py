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

from . import io as bio


class BIDSTree:

    def __init__(self, dataset_dir, overwrite=False):

        print('Initializing BIDS dataset directory tree in %s' % dataset_dir)

        self.bids_dir = dataset_dir
        self.sourcedata_dir = os.path.join(dataset_dir, 'sourcedata')
        self.derivatives_dir = os.path.join(dataset_dir, 'derivatives')
        self.code_dir = os.path.join(dataset_dir, 'code')
        self.work_dir = os.path.join(dataset_dir, 'work')

        # sourcedata should already exist - no need to create
        # Existence check in __main__

        # Create required directories
        # Note: sourcedata/ must already be present and filled with DICOM images
        bio.safe_mkdir(self.derivatives_dir)
        bio.safe_mkdir(self.code_dir)
        bio.safe_mkdir(self.work_dir)

        self.translator_file = os.path.join(self.code_dir, 'Protocol_Translator.json')

        print('Creating required file templates')

        # README file
        self.readme_file = os.path.join(dataset_dir, 'README')
        with open(self.readme_file, 'w') as fd:
            fd.writelines('Useful information about this dataset\n')

        # CHANGES changelog file
        self.changes_file = os.path.join(dataset_dir, 'CHANGES')
        with open(self.changes_file, 'w') as fd:
            fd.writelines(['1.0.0 YYYY-MM-DD\n', ' - Initial release\n'])

        # Create template JSON dataset description (must comply with BIDS 1.2 spec)
        self.datadesc_json = os.path.join(self.bids_dir, 'dataset_description.json')
        meta_dict = dict({
            'Name': 'Descriptive name for this dataset',
            'BIDSVersion': '1.2',
            'License': 'This data is made available under the Creative Commons BY-SA 4.0 International License.',
            'Authors': ['First Author', 'Second Author'],
            'Acknowledgments': 'Thanks to everyone for all your help',
            'HowToAcknowledge': 'Please cite: Author AB, Seminal Paper Title, High Impact Journal, 2019',
            'Funding': ['First Grant', 'Second Grant'],
            'ReferencesAndLinks': ['A Reference', 'Another Reference', 'A Link'],
            'DatasetDOI': '10.0.1.2/abcd.10'
        })
        bio.write_json(self.datadesc_json, meta_dict, overwrite)

        # Create participants JSON file defining columns in participants.tsv
        # See
        self.participants_json = os.path.join(self.bids_dir, 'participants.json')
        meta_dict = dict({
            'age': {
                'Description': 'Age of participant',
                'Units': 'years'
            },
            'sex': {
                'Description': 'Sex of participant',
                'Levels': {
                    'M': 'male',
                    'F': 'female',
                    'T': 'transgender'
                }
            },
            'group': {
                'Description': 'participant group assignment'
            },
        })
        bio.write_json(self.participants_json, meta_dict, overwrite)

        # Create .bidsignore file to skip work/ during validation
        self.ignore_file = os.path.join(dataset_dir, '.bidsignore')
        with open(self.ignore_file, 'w') as fd:
            fd.writelines('work/\n')

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
