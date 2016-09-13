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

1. Organize DICOM Data
Organize the source DICOM data into separate subject directories within a root DICOM folder. The DICOM image files do not need to be organized heirarchically within each subject directory. This might look something like the following (where AAnnnn is the subject ID:

mydicom/
   |- AA0100/
      img-0001-0001.dcm
      img-0001-0002.dcm
       ...
   |- AA0101/
      img-0001-0001.dcm
      img-0001-0002.dcm
      ...

2. FIRST PASS CONVERSION. Run dcm2niix on the root DICOM folder and specify an output root BIDS folder for the converted files. The first pass conversion will create a template dictory (Protocol_Translator.json) in the root DICOM folder.

3. Edit the translator dictionary. 

4. SECOND PASS CONVERSION
