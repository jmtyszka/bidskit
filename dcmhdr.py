#!/usr/bin/env python3
"""
Convert flat DICOM file set into a BIDS-compliant Nifti structure
- Expects protocol names to be in BIDS format (eg task-rest_run-01_bold)

Usage
----
dcm2bids.py -i <DICOM Directory> -o <BIDS Directory Root>

Example
----
% dcm2bids.py -i mydicom -o mybids

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2016-08-03 JMT From scratch

MIT License

Copyright (c) 2016 Mike Tyszka

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

__version__ = '0.9.1'

import os
import sys
import argparse
import subprocess
import shutil
import json
import dicom
import glob
from datetime import datetime as dt


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Extract useful fields from DICOM headers')
    parser.add_argument('-i','--input', required=True, nargs='+', help='List of DICOM filenames')
    parser.add_argument('-o','--output', help='Output CSV file name')

    # Parse command line arguments
    args = parser.parse_args()

    # List of one or more DICOM files
    dcm_fnames = args.input

    if args.output:
        csv_fname = args.output
    else:
        csv_fname = 'dicom_table.csv'

    # Open output CSV file
    try:
        csv_fd = open(csv_fname, 'w')
    except:
        print('* Problem opening output CSV file')
        sys.exit(1)


    # Write header row to CSV file
    hdr_str = 'Filename, PatName, Sex, Age, SerNo, SerDesc, AcqDateTime\n'
    sys.stdout.write(hdr_str)
    sys.stdout.flush()
    csv_fd.write(hdr_str)

    # Loop over each subject's DICOM directory within the root source directory
    for dcm_fname in dcm_fnames:

        if os.path.isfile(dcm_fname):

            # Get subject age and sex from representative DICOM header
            hdr = dcm_hdr(dcm_fname)

            # Add line to CSV output file
            line_str = '%s, %s, %s, %s, %s, %s, %s\n' % (
                dcm_fname,
                hdr['PatName'],
                hdr['Sex'],
                hdr['Age'],
                hdr['SerNo'],
                hdr['SerDesc'],
                hdr['AcqDateTime']
            )
            sys.stdout.write(line_str)
            sys.stdout.flush()
            csv_fd.write(line_str)

        else:

            print('* Could not find DICOM file %s - skipping' % dcm_fname)

    # Close participants TSV file
    csv_fd.close()

    # Clean exit
    sys.exit(0)


def dcm_hdr(dcm_fname):
    """
    Extract relevant subject information from DICOM header
    :param dcm_fname: DICOM filename
    :return dcm_info: DICOM header information dictionary
    """

    try:
        ds = dicom.read_file(dcm_fname, force=True)
    except:
        print("Unexpected error:", sys.exc_info()[0])
        raise

    # Init a new dictionary
    hdr = dict()

    if ds:

        # Fill dictionary
        hdr['PatName'] = ds.PatientName
        hdr['SerNo'] = ds.SeriesNumber
        hdr['SerDesc'] = ds.SeriesDescription
        hdr['AcqDateTime'] = dcm_date_time(ds.AcquisitionDate, ds.AcquisitionTime)
        hdr['Sex'] = ds.PatientSex
        hdr['Age'] = ds.PatientAge

    else:

        print('* No DICOM header information found in %s' % dcm_dir)
        print('* Confirm that this DICOM image is uncompressed')
        print('* Exiting')
        sys.exit(1)


    return hdr


def dcm_date_time(dcm_date, dcm_time):

    # DICOM date is in form YYYYMMDD
    # DICOM time is form HHMMSS.mmm

    d = dt.strptime(dcm_date + dcm_time, '%Y%m%d%H%M%S.%f')

    return str(d)

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
