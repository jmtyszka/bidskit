# BIDSKIT Changelog

## Version 2024.11.22
- Fixed pydicom handling of extended DICOM. Credit to Hu Cheng @ Indiana University

## Version 2024.11.7
- Minor bug fixes for --auto with non-ReproIn series descriptions

## Version 2024.5.4
- Add bidsdump and bidsmeta utility commands to bin/ folder

## Version 2024.1.12
- Fix sessions argument handling

## Version 2023.8.25
- Update Flywheel option to autodetect new .zip download archives

## Version 2023.2.16
- Fixed ses_clean error with --no-sessions

## Version 2023.1.26
- Fixed folder name handling for Web vs CLI Flywheel DICOM downloads

## Version 2023.1.12
- Add support for Flywheel DICOM download curation

## Version 2022.2.1
- Added support for complex-valued, bias corrected and multiecho image types
- Added command line control for rec-, echo- and part- keys in BIDS filenames

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