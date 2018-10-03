# bidskit 
Python utilities for converting from DICOM to BIDS and NDAR-compliant neuroimaging formats.

[![DOI](https://zenodo.org/badge/64889181.svg)](https://zenodo.org/badge/latestdoi/64889181)

## dcm2bids.py (current version 1.1.2)
Python script which takes a directory tree containing imaging series from one or more subjects (eg T1w MPRAGE, BOLD EPI, Fieldmaps), converts the imaging data to Nifti-1 format with JSON metadata files (sidecars) and populates a
Brain Imaging Data Structure (BIDS) which should pass the online BIDS validation tool (http://incf.github.io/bids-validator).

## Installation

There are two options available for installation and running the BIDS conversion:

### Docker Image 
(This assumes you have Docker installed on your system (https://docs.docker.com/engine/installation/)

Simply pull the docker image of this app from Docker Hub and point to your DICOM folders as below:

<pre> docker pull rnair07/bidskit </pre> (This downloads the bidskit docker image to your system)

You could also skip the above step and directly run the command below instead and it will automatically pull the image for you + run the conversion.

<pre> docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/DICOM --outdir=/mnt/BIDS </pre>

where PATH_TO_YOUR_RAW_DICOM is the *root directory* containing the *mydicom* folder as shown in the file structure below. 

### From Source
Clone the repository, add the resulting directory to your path and install dependencies mentioned below (_Will upgrade this to a python setup soon_).

<pre>
% git clone https://github.com/jmtyszka/bidskit.git
</pre>

**Dependencies**
This release was developed under Python 3.6 (os, sys, argparse, subprocess, shutil, json, glob). Other dependencies include:
1. pydicom 1.0.1 (latest version in PyPi)
2. Chris Rorden's dcm2niix - the latest version at the time of writing is v1.0.20171103 ([source](https://github.com/rordenlab/dcm2niix) or [precompiled binaries](https://www.nitrc.org/frs/?group_id=889))

## DICOM to BIDS Conversion

### Organize DICOM Data

Organize the source DICOM images into separate subject and subject-session directories within a root directory (`mydicom` in the example below, but the script default is simply `dicom`). The organization of DICOM files within each subject directory can follow a session-series heirarchy or by a simple flat directory containing all subject files. The conversion to Nifti-1 format and JSON sidecar generation is handled by dcm2niix, so whatever works for dcm2niix will hopefully work for dcm2bids.py. A typical DICOM directory tree might look something like the following (where "Ra0950" and "Ra0951" are subject IDs and "first", "second" are session names for each subject):

<pre>
mydicom
└── Ra0950
    └── first
        ├── IM-0001-0001.dcm
        ├── IM-0001-0002.dcm
        ...
    └── second
        ...
└── Ra0951
    └── first
        ├── IM-0001-0001.dcm
        ├── IM-0001-0002.dcm
        ...
    └── second
        ...
</pre>


### First Pass Conversion
The required command line arguments and defaults for dcm2bids.py can be displayed using:
<pre>
% dcm2bids.py -h
usage: dcm2bids.py [-h] [-i INDIR] [-o OUTDIR] [--no-sessions]

Convert DICOM files to BIDS-compliant Nifty structure

optional arguments:
  -h, --help            show this help message and exit
  -i INDIR, --indir INDIR
                        DICOM input directory with Subject/Session/Image
                        organization [dicom]
  -o OUTDIR, --outdir OUTDIR
                        Output BIDS source directory [source]
  --no-sessions         Do not use session sub-directories
</pre>

Note that the defaults for the input DICOM and output BIDS directories are `dicom` and `source` respectively. So the simplest possible setup would be to place subject DICOM folders within a directory called `dicom` and run dcm2bids.py from the parent directory of `dicom`. This would generate a BIDS source directory called `source`, a BIDS derivatives directory called `derivatives` with a `conversion` subdirectory containing a protocol translator JSON file and a working directory called `work`.

If you're using the Docker image, run the following:
<pre>
docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/dicom --outdir=/mnt/source
</pre>

If you're running dcm2bids.py locally from source, you can use any of the following:
<pre>
% dcm2bids.py
% dcm2bids.py -i mydicom
% dcm2bids.py -i mydicom -o mysource
</pre>

The first pass conversion will create new translator dictionary (Protocol_Translator.json) in the root DICOM folder. This has been prefilled with the protocol series names from the DICOM header of all unique series detected in the original DICOM files. The command will also create the new BIDS directory containing a single temporary conversion directory containing Nifti images and JSON sidecars for all series in the source DICOM folder:

<pre>
derivatives/
└── conversion/
    ├── Protocol_Translator.json
dicom/
└── Ra0950
    └── first/
        └── ...    
    └── second/
        └── ...    
└── Ra0951
    └── first/
        └── ...    
    └── second/
        └── ...    
source/
work/
└── conversion/
    └── sub-Ra0950/
        └── ses-first/
            ├── sub-Ra0950_ses-first_....nii.gz
            ├── sub-Ra0950_ses-first_....json

            
</pre>

#### Conversion without Sessions
You can omit the use of session subdirectories if you only have one session per subject. Use the --no-sessions command line flag to achieve this (this feature is switched off by default):
<pre>
% dcm2bids.py --no-sessions -i mydicom -o mybids
</pre>

### Edit Translator Dictionary

dcm2bids.py creates a JSON series name translator in the derivatives/conversion folder. You'll use this file to specific how you want individual series data to be renamed into the output BIDS source directory. Open the Protocol_Translator.json file in a text editor. Initially it will look something like the following, with the BIDS directory, filename suffix and IntendedFor fields set to their default values of "EXCLUDE_BIDS_Name", "EXCLUDE_BIDS_Directory" and 
"UNASSIGNED" (the double quotes are a JSON requirement):

<pre>
{
    "Localizer":[
        "EXCLUDE_BIDS_Directory"
        "EXCLUDE_BIDS_Name",
        "UNASSSIGNED"
    ],
    "rsBOLD_MB_1":[
        "EXCLUDE_BIDS_Directory"
        "EXCLUDE_BIDS_Name",
        "UNASSSIGNED"
    ],
    "T1_2":[
        "EXCLUDE_BIDS_Directory"
        "EXCLUDE_BIDS_Name",
        "UNASSSIGNED"
    ],
    "Fieldmap_rsBOLD":[
        "EXCLUDE_BIDS_Directory"
        "EXCLUDE_BIDS_Name",
        "UNASSSIGNED"
    ],
    ...
}
</pre>

The IntendedFor field is only relevant for fieldmap series and links the fieldmap to one or more EPI series for distortion correction.

Edit the BIDS directory and filename suffix entries for each series with the BIDS-compliant filename suffix (excluding the sub-xxxx_ses-xxxx_ prefix and any file extensions) and the BIDS purpose directory name (anat, func, fmap, etc). In the example above, this might look something like the following:

<pre>
{
    "Localizer":[
        "EXCLUDE_BIDS_Directory",
        "EXCLUDE_BIDS_Name",
        "UNASSIGNED"
    ],
    "rsBOLD_MB_1":[
        "func",
        "task-rest_acq-MB_run-01_bold",
        "UNASSIGNED"
    ],
    "T1_2":[
        "anat",
        "run-02_T1w",
        "UNASSIGNED"
    ],
    "Fieldmap_rsBOLD":[
        "fmap",
        "acq-rest",
        ["task-rest_acq-MB_run-01_bold", "task-rest_acq-MB_run-02_bold"]
    ],
    ...
}
</pre>

Complete documentation for the BIDS standard, including appropriate filenaming conventions, can be found at http://bids.neuroimaging.io

### Second Pass Conversion
The bidskit now has enough information to correctly organize the converted Nifti images and JSON sidecars into a BIDS directory tree. Any protocol series with a BIDS name or directory begining with "EXCLUDE" will be skipped (useful for excluding localizers, teleradiology acquisitions, etc from the final BIDS directory). Rerun the docker command or dcm2bids.py (use the same command as in the first pass):

If your using the Docker image, run the following:
<pre>
% docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/dicom --outdir=/mnt/source
</pre>

If you're running the script locally, run something similar to the following depending on the command that was run for Phase 1:
<pre>
% dcm2bids.py -i mydicom -o mysource
</pre>

This will populate the BIDS source directory from the working conversion directory:

<pre>
source
├── dataset_description.json
├── participants.tsv
└── sub-Ra0950
    └── ses-first
        ├── anat
        │   ├── sub-Ra0950_run-01_T1w.json
        │   ├── sub-Ra0950_run-01_T1w.nii.gz
        │   ├── sub-Ra0950_run-02_T1w.json
        │   └── sub-Ra0950_run-02_T1w.nii.gz
        ├── fmap
        │   ├── sub-Ra0950_acq-fmap_magnitude1.nii.gz
        │   ├── sub-Ra0950_acq-fmap_phasediff.json
        │   └── sub-Ra0950_acq-fmap_phasediff.nii.gz
        └── func
            ├── sub-Ra0950_task-rest_acq-MB_run-01_bold.json
            ├── sub-Ra0950_task-rest_acq-MB_run-01_bold.nii.gz
            ├── sub-Ra0950_task-rest_acq-MB_run-01_events.tsv
            ├── sub-Ra0950_task-rest_acq-MB_run-02_bold.json
            ├── sub-Ra0950_task-rest_acq-MB_run-02_bold.nii.gz
            └── sub-Ra0950_task-rest_acq-MB_run-02_events.tsv
</pre>

bidskit attempts to sort the fieldmap data appropriately into magnitude and phase images (for multi-echo GRE fieldmaps), or phase-encoding reversed pairs (for SE-EPI fieldmapping). The resulting dataset_description.json and functional event timing files (func/*_events.tsv) will need to be edited by the user, since the DICOM data contains no information about the design or purpose of the experiment.

## Bugs, Feature Requests and Comments 
Please use the GitHub Issues feature to raise issues with the bidskit repository (https://github.com/jmtyszka/bidskit/issues)
