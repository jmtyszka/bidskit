# BIDSKIT Changelog

## Version 1.2.3

## Version 1.2.2
- Fixed auto run number issue #55

## Version 1.2.1

- Bring output directory structure into compliance with BIDS v1.2
- Old source/ directory contents raised to top level of BIDS dataset directory
- dicom/ renamed to sourcedata/
- derivatives/ moved to top level of BIDS dataset directory
- Added appropriate README templates
- Updated dataset_description.json template
- Move Protocol_Translator.json to new code/ directory
- Add verifier from bids_verifier module
- Reconfigure as class-based python package

## Version 1.1.3
- Fixes run number ordering issues

## Version 1.1.2
- Fixes minor issues with run numbering, file overwrites and docker

## Version 1.1.1
- Fixed single-band reference (sbref) handling for Siemens multiband acquisitions
- Fixed run number inference in the presence of duplicate series descriptions
- Fixed file path issues with fieldmap IntendedFor value in JSON sidecars

## Version 1.0.0
- Initial public release
- TaskName and IntendedFor tag support
- DWI support
- work/ directory for intermediate conversion files
- "no session" mode