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

### Organize DICOM Data

Organize the source DICOM data into separate subject directories within a root DICOM folder. The DICOM image files do not need to be organized heirarchically within each subject directory. This might look something like the following (where RaXXXX are subject IDs:

<pre>
mydicom
└── Ra0950
    ├── IM-0001-0001.dcm
    ├── IM-0001-0002.dcm
    ...
└── Ra0951
    ├── IM-0001-0001.dcm
    ├── IM-0001-0002.dcm
    ...
</pre>

### First Pass Conversion

Run dcm2niix on the root DICOM folder and specify an output root BIDS folder for the converted files.

<pre>
% dcm2bids.py -i mydicom -o bids
</pre>

The first pass conversion will create new translator dictionary (Protocol_Translator.json) in the root DICOM folder. This has been prefilled with the protocol series names from the DICOM header of all unique series detected in the original DICOM files.

<pre>
dicom
├── Protocol_Translator.json
└── Ra0950
    ├── ...
└── Ra0951
    ├── ...
</pre>

### Edit Translator Dictionary

Open Protocol_Translator.json in a text editor. Initially it will look something like the following, with the series name and directory fields set to their default values of "EXCLUDE_BIDS_Name" and "EXCLUDE_BIDS_Directory" (the double quotes a JSON requirement):

<pre>
{
    "Localizer":[
        "EXCLUDE_BIDS_Name",
        "EXCLUDE_BIDS_Directory"
    ],
    "rsBOLD_MB_1":[
        "EXCLUDE_BIDS_Name",
        "EXCLUDE_BIDS_Directory"
    ],
    "T1_2":[
        "EXCLUDE_BIDS_Name",
        "EXCLUDE_BIDS_Directory"
    ],
    ...
}
</pre>

Edit the BIDS name and directory values with the BIDS-compliant filename (excluding the sub-xxxx prefix) and the BIDS purpose directory name (anat, func, fmap, etc). In the example above, this might look something like the following:

<pre>
{
    "Localizer":[
        "EXCLUDE_BIDS_Name",
        "EXCLUDE_BIDS_Directory"
    ],
    "rsBOLD_MB_1":[
        "task-rest_acq-MB_run-1_bold",
        "func"
    ],
    "T1_2":[
        "run-2_T1w",
        "anat"
    ],
    ...
}
</pre>

For complete documentation for the BIDS standard, including appropriate filenaming conventions, can be found at http://bids.neuroimaging.io

### Second Pass Conversion
