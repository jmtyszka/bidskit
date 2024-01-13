# Quick Start Guide

## DICOM to BIDS Conversion

### Initial organization of the BIDS dataset directory
BIDSKIT attempts to track the
[BIDS Specification](https://bids-specification.readthedocs.io/en/stable/)
as closely as possible.
We recommend checking out the
[BIDS Starter Kit](https://github.com/bids-standard/bids-starter-kit/wiki/The-BIDS-folder-hierarchy)
for concrete examples of BIDS formatted datasets.

To start out, you should create a dataset folder with a semi-descriptive name (eg learning_pilot_2019)
with a sourcedata/ subfolder containing your raw DICOM data, organized by subject, or by subject and session.
A typical DICOM directory tree might look something like the following, where *Cc0001*, *Cc0002* are subject IDs
and *first*, "second" are session names.

<pre>
learning_pilot_2019/
├── sourcedata
│   ├── Cc0001
│   │   ├── first
│   │   │   └── [DICOM Images]
│   │   └── second
│   │       └── [DICOM Images]
│   └── Cc0002
│   │   ├── first
│   │   │   └── [DICOM Images]
│   │   └── second
│   │       └── [DICOM Images]
...
</pre>

DICOM image files within each session directory can be in a simple flat organization or within individual series subfolders.

That's all you need to do in terms of organizing your raw DICOM data. The next phase will generate an editable translator file
which controls the conversion of your original MRI series into a BIDS-compliant directory tree.

### First Pass Conversion

If you're using the Docker image, run the following:
```bash
docker run -it -v /PATH_TO_YOUR_DATASET_FOLDER/:/dataset jmtyszka/bidskit bidskit -d /dataset
```
For Mac M1 user, build your image with argument `--platform linux/amd64`
```bash
# cd to root dir which contains Dockerfile
docker build --platform linux/amd64 -t bidskit:latest .
docker run -it -v --name bidskit /PATH_TO_YOUR_DATASET_FOLDER/:/dataset bidskit:latest -d /dataset
```

If you're running *bidskit* from the shell you can either run *bidskit* without arguments from within the `/dataset` root
```bash
cd /PATH_TO_YOUR_DATASET_FOLDER/
bidskit
```

or from another folder by specifying the BIDS dataset directory

```bash
bidskit -d /PATH_TO_YOUR_DATASET_FOLDER/
```

The first pass conversion constructs a BIDS-compliant directory tree around sourcedata/ with required text files,
including a translator dictionary (Protocol_Translator.json) in the `code/` subdirectory:

#### BIDS Dataset after First Pass Conversion
<pre>
learning_pilot_2019/
├── CHANGES
├── README
├── code
│   └── Protocol_Translator.json
├── dataset_description.json
├── derivatives
├── participants.json
├── participants.tsv
├── sourcedata
│   ├── Cc0001
│   │   ├── first
│   ...
│   
│   └── Cc0002
│   ...
│   
└── work
    ├── sub-Cc0001
    │   ├── ses-first
    │   └── ses-second
    └── sub-Cc0002
        ├── ses-first
        └── ses-second         
</pre>

#### Conversion without Sessions
You can omit the use of session subdirectories if you only have one session per subject. Use the --no-sessions command line flag to achieve this (this feature is switched off by default):
```bash
bidskit -d /PATH_TO_YOUR_DATASET_FOLDER/ --no-sessions
```

### Editing the Translator Dictionary

Before diving into editing the translator dictionary we recommend a passing familiarity with the
[BIDS Specification](https://bids-specification.readthedocs.io/en/stable/)
and [BIDS Starter Kit](https://github.com/bids-standard/bids-starter-kit/wiki/The-BIDS-folder-hierarchy)

The Protocol_Translator.json file lets *bidskit* know how you want to map individual series data to the BIDS format.
Open Protocol_Translator.json file in your favorit text editor. Initially it will look something
like the following, with the BIDS directory, filename suffix and IntendedFor fields set to their default values
of "EXCLUDE_BIDS_Name", "EXCLUDE_BIDS_Directory" and "UNASSIGNED" (the double quotes are a JSON requirement):

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

The IntendedFor field is only relevant for fieldmap series and specifies which EPI series (BOLD, DWI, etc) are to be
distortion corrected by given fieldmap data.

Edit the BIDS directory and filename suffix entries for each series with the BIDS-compliant filename suffix
(excluding the sub-xxxx_ses-xxxx_ prefix and any file extensions) and the BIDS purpose directory name
(anat, func, fmap, etc). In the example above, this might look something like the following:

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

### Second Pass Conversion
*bidskit* now has enough information to organize the converted Nifti images and JSON sidecars in the work/ folder
according to the BIDS specification.
Any protocol series in Protocol_Translator.json with a BIDS name or directory begining with "EXCLUDE" will be skipped
(useful for excluding localizers, teleradiology acquisitions, etc from the final BIDS directory).

You can simply run the same *bidskit* or *docker* command used for the first pass.
*bidskit* will detect the protocol translator and the converted image data in the work/ folder from the first pass above.
This will populate the *sub-* directories and participants.tsv file at the dataset root level:

#### BIDS Dataset after Second Pass Conversion
<pre>
learning_pilot_2019/
├── CHANGES
├── README
├── code
│   └── Protocol_Translator.json
├── dataset_description.json
├── derivatives
├── participants.json
├── participants.tsv
├── sourcedata
│   ├── Cc0001
│   │   ├── first
│   ...
│   
│   └── Cc0002
│   ...
│   
├── sub-Cc0001
│   ├── ses-first
│   │   ├── anat
│   │   ├── dwi
│   │   ├── fmap
│   │   └── func
│   └── ses-second
│   ...
│   
├── sub-Cc0002
│   ├── ses-first
│   ...
│   
└── work
    ├── sub-Cc0001
    │   ├── ses-first
    │   └── ses-second
    └── sub-Cc0002
        ├── ses-first
        └── ses-second
</pre>

### Loose Ends
Only so much information can be extracted from the DICOM image files and there are some pieces of infomation that only
the user can provide. For example *dataset_description.json* and task timing files (*func/..._events.tsv*) are
just templates and must be completed by the user. Again, you should refer to the
[BIDS Specification](https://bids-specification.readthedocs.io/en/stable/) for full details of the expected format of
these files.

## Bugs and Feature Requests 
Good luck and let us know about bugs and feature requests through this repo's
[GitHub Issues](https://github.com/jmtyszka/bidskit/issues) page.
