"""
Class for creating and managing BIDS directory tree and essential files
"""

import os
import json
import bidskit.io as bio
from datetime import datetime as dt


class BIDSTree():

    def __init__(self, dataset_dir, overwrite=False):

        print('Initializing BIDS dataset directory tree in %s' % dataset_dir)

        self.bids_dir = dataset_dir
        self.derivatives_dir = os.path.join(dataset_dir, 'derivatives')
        self.sourcedata_dir = os.path.join(dataset_dir, 'sourcedata')
        self.code_dir = os.path.join(dataset_dir, 'code')
        self.work_dir = os.path.join(dataset_dir, 'work')

        bio.safe_mkdir(self.derivatives_dir)
        bio.safe_mkdir(self.sourcedata_dir)
        bio.safe_mkdir(self.code_dir)
        bio.safe_mkdir(self.work_dir)

        self.translator_file = os.path.join(self.code_dir, 'Protocol_Translator.json')

        print('Creating required file templates')

        # README file
        self.readme_file = os.path.join(dataset_dir, 'README')
        with open(self.readme_file, 'w') as fd:
            fd.writelines('Useful information about this dataset')

        # CHANGES changelog file
        self.changes_file = os.path.join(dataset_dir, 'CHANGES')
        with open(self.changes_file, 'w') as fd:
            fd.writelines('Dataset directory created %s' % str(dt.now()))

        # Create template JSON dataset description (must comply with BIDS spec)
        datadesc_json = os.path.join(self.bids_dir, 'dataset_description.json')
        meta_dict = dict({
            'BIDSVersion': "1.2",
            'License': "This data is made available under the Creative Commons BY-SA 4.0 International License.",
            'Name': "The dataset name goes here",
            'ReferencesAndLinks': "References and links for this dataset go here"})

        # Write JSON file
        bio.write_json(datadesc_json, meta_dict, overwrite)


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
            print('For example "MP-RAGE T1w 3D structural" or "MB-EPI BOLD resting-state')
            print('---')
            print('')

        return


    def read_translator(self):
        """
        Read protocol translations from JSON file in DICOM directory

        :param prot_dict_json: string
            JSON protocol translation dictionary filename
        :return:
        """

        if os.path.isfile(self.translator_file):

            # Read JSON protocol translator
            json_fd = open(self.translator_file, 'r')
            translator = json.load(json_fd)
            json_fd.close()

        else:

            translator = dict()

        return translator



