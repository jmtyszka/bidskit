## Useful features and typical use cases

### Adding new subjects to an existing BIDS folder
This is a very common task during an ongoing experiment. If you have acquired DICOM data from a new subject (eg S999) and wish to add this subject to the existing
BIDS dataset folder, first create a new subject folder with an optional session subfolder in the sourcedata folder:
```
.
├── CHANGES
├── README
├── code
│   └── Protocol_Translator.json
├── dataset_description.json
├── derivatives
├── participants.json
├── participants.tsv
├── sourcedata
│   ├── S123
│   │   └── 1
│   └── S999    * New subject/session DICOM folder *
│       └── 1
├── sub-S123
│   └── ses-1
│       └── func
└── work
    └── sub-S123
        └── ses-1
```
Now re-run bidskit with the `--subject` argument set to S999.
```
bidskit --subject S999
```
The resulting tree should look like this
```
.
├── CHANGES
├── README
├── code
│   └── Protocol_Translator.json
├── dataset_description.json
├── derivatives
├── participants.json
├── participants.tsv
├── sourcedata
│   ├── S123
│   │   └── 1
│   └── S999
│       └── 1
├── sub-S123
│   └── ses-1
│       └── func
├── sub-S999
│   └── ses-1
│       └── func
└── work
    ├── sub-S123
    │   └── ses-1
    └── sub-S999
        └── ses-1
```
The --subject argument supports space-separated lists of subject IDs (without the sub- prefix) if you need to add multiple new subjects.
