# bidskit 
Python utilities for converting from DICOM to BIDS and NDAR-compliant neuroimaging formats.

## dcm2bids.py
Python 3.4 function which takes a flat DICOM directory containing multiple imaging series (eg T1w MPRAGE, BOLD EPI, Fieldmaps)
and converts into a Brain Imaging Data Structure which should pass the online BIDS validation tool (http://incf.github.io/bids-validator).

## Installation

We have two options available for installation and running the BIDS conversion:

**1. Using the Docker image:** Simply pull the docker image of this app from Docker Hub and point to your DICOM folders as below:

<pre> docker pull rnair07/bidskit </pre> (This downloads the bidskit docker image to your system)

You could also skip the above step and directly run the command below instead and it will automatically pull the image for you + run the conversion.

<pre> docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/DICOM --outdir=/mnt/BIDS </pre>

where PATH_TO_YOUR_RAW_DICOM is the *root directory* containing the *mydicom* folder as shown in the file structure below. 

**OR**

**2. Download the repo and install dependencies:** Clone the repository, add the resulting directory to your path and install dependencies mentioned below (_Will upgrade this to a python setup soon_).

<pre>
% git clone https://github.com/jmtyszka/bidskit.git
</pre>

**Dependencies**
This release was developed under Python 3.5 (os, sys, argparse, subprocess, shutil, json, glob). Other dependencies include:
1. pydicom 0.9.9 (latest version in PyPi)
2. Chris Rorden's dcm2niix v1.0.20170624 or greater ([source](https://github.com/rordenlab/dcm2niix) or [precompiled binaries](https://www.nitrc.org/frs/?group_id=889))

## Converting from DICOM to BIDS

### Organize DICOM Data

Organize the source DICOM images into separate subject and subject-session directories within a root directory (mydicom in the example below). The DICOM image files do not need to be organized heirarchically within each subject-sesssion directory. This might look something like the following (where "Ra0950" and "Ra0951" are subject IDs and "first", "second" are session names for each subject):

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

Run the docker image or dcm2niix on the root DICOM folder and specify an output root BIDS folder for the converted files.

With the docker image, do:
<pre>
docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/DICOM --outdir=/mnt/BIDS
</pre>

Else, if you downloaded the source and set up your local env., do:
<pre>
% dcm2bids.py -i mydicom -o mybids
</pre>

The first pass conversion will create new translator dictionary (Protocol_Translator.json) in the root DICOM folder. This has been prefilled with the protocol series names from the DICOM header of all unique series detected in the original DICOM files. The command will also create the new BIDS directory containing a single temporary conversion directory containing Nifti images and JSON sidecars for all series in the source DICOM folder:

<pre>
mydicom
├── Protocol_Translator.json
└── Ra0950
    └── ses-first
        └── ...    
    └── ses-second
        └── ...    
└── Ra0951
    └── ses-first
        └── ...    
    └── ses-second
        └── ...    
mybids
└── conv
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
    "Fieldmap_rsBOLD":[
        "acq-fmap",
        "fmap"
    ],
    ...
}
</pre>

Edit the BIDS name and directory values with the BIDS-compliant filename (excluding the sub-xxxx prefix) and the BIDS purpose directory name (anat, func, fmap, etc). In the example above, this might look something like the following:

<pre>
{
    "Localizer":[
        "EXCLUDE_BIDS_Directory",
        "EXCLUDE_BIDS_Name"
    ],
    "rsBOLD_MB_1":[
        "func",
        "task-rest_acq-MB_run-1_bold"
    ],
    "T1_2":[
        "anat",
        "run-2_T1w"
    ],
    ...
}
</pre>

For complete documentation for the BIDS standard, including appropriate filenaming conventions, can be found at http://bids.neuroimaging.io

### Second Pass Conversion
The bidskit now has enough information to correctly organize the converted Nifti images and JSON sidecars into a BIDS directory tree. Any protocol series with a BIDS name or directory begining with "EXCLUDE" will be skipped (useful for excluding localizers, teleradiology acquisitions, etc from the final BIDS directory). Rerun the docker command or dcm2bids.py (use the same command as in the first pass):

With the docker image, do:
<pre>
docker run -it -v /PATH_TO_YOUR_RAW_DICOM_FOLDER/:/mnt rnair07/bidskit --indir=/mnt/DICOM --outdir=/mnt/BIDS
</pre>

Else, if you're running the script locally, do:
<pre>
% dcm2bids.py -i mydicom -o mybids
</pre>

This will copy and rename all files generated in the first pass into the output BIDS directory (mybids), which will now look something like this:

<pre>
bids
├── dataset_description.json
├── participants.tsv
└── sub-Ra0950
    └── ses-first
        ├── anat
        │   ├── sub-Ra0950_run-1_T1w.json
        │   ├── sub-Ra0950_run-1_T1w.nii.gz
        │   ├── sub-Ra0950_run-2_T1w.json
        │   └── sub-Ra0950_run-2_T1w.nii.gz
        ├── fmap
        │   ├── sub-Ra0950_acq-fmap_magnitude1.nii.gz
        │   ├── sub-Ra0950_acq-fmap_phasediff.json
        │   └── sub-Ra0950_acq-fmap_phasediff.nii.gz
        └── func
            ├── sub-Ra0950_task-rest_acq-MB_run-1_bold.json
            ├── sub-Ra0950_task-rest_acq-MB_run-1_bold.nii.gz
            ├── sub-Ra0950_task-rest_acq-MB_run-1_events.tsv
            ├── sub-Ra0950_task-rest_acq-MB_run-2_bold.json
            ├── sub-Ra0950_task-rest_acq-MB_run-2_bold.nii.gz
            └── sub-Ra0950_task-rest_acq-MB_run-2_events.tsv
</pre>

bidskit attempts to sort the Fieldmap data appropriately into magnitude and phase images. The resulting dataset_description.json and functional event timing files (func/*_events.tsv) will need to be edited by the user, since the DICOM data contains no information about the design or purpose of the experiment.

## Bugs, Feature Requests and Comments 

Please use the GitHub Issues feature to raise issues with the bidskit repository (https://github.com/jmtyszka/bidskit/issues)
