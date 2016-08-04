#!/usr/bin/env python3
"""
Convert flat DICOM file set into a BIDS-compliant Nifti structure

Usage
----
dcm2bids.py -i <DICOM Directory> -o <BIDS Directory Root>

Example
----
% dcm2bids.py -i DICOM -o Experiment

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

__version__ = '0.1.0'

import sys
import argparse
import nibabel as nib
import numpy as np
import pandas as pd


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to BIDS-compliant Nifty structure')
    parser.add_argument('-i','--indir', required=True, help='Input directory containing flat DICOM images')
    parser.add_argument('-o','--outdir', required=True, help='Output BIDS directory root')

    # Parse command line arguments
    args = parser.parse_args()

    indir = args.indir
    outdir = args.outdir

    print('Converting DICOM images from %s' % indir)

    # Clean exit
    sys.exit(0)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
