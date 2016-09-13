# bidskit
Python utilities for converting fromh DICOM to BIDS and NDAR-compliant neuroimaging formats.

## dcm2bids.py
Python 3.4 function which takes a flat DICOM directory containing multiple imaging series (eg T1w MPRAGE, BOLD EPI, Fieldmaps)
and converts into a Brain Imaging Data Structure which should pass the online BIDS validation tool (http://incf.github.io/bids-validator).

## Dependencies
Python 3.4
Python packages:
Caltech branch of the dcm2niix tool (https://github.com/jmtyszka/dcm2niix)

## Installation

## Quick start

### Organize all DICOM data into separate subject directories within a root DICOM folder. The DICOM image files do not need to be organized heirarchically within each subject directory.

### FIRST PASS CONVERSION. Run dcm2niix on the root DICOM folder and specify an output root BIDS folder for the converted files. The first pass conversion will create a template dictory (Protocol_Translator.json) in the root DICOM folder.

### Edit the translator dictionary. 

### SECOND PASS CONVERSION
