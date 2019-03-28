# BIDSKIT 1.2.3 DEVELOPMENT 
Python utilities for converting from DICOM to BIDS neuroimaging formats.

The *bidskit* console command takes a directory tree containing imaging series from one or more subjects (eg T1w MPRAGE, BOLD EPI, Fieldmaps), converts the imaging data to Nifti-1 format with JSON metadata files (sidecars) and populates a
Brain Imaging Data Structure (BIDS) which should pass the online BIDS validation tool (http://incf.github.io/bids-validator).

The version numbering for bidskit follows that of the BIDS specification it implements. At the time of writing, BIDS and bidskit are at version 1.2.

## Documentation
#### [Installation Instructions](docs/Installation.md)
#### [Quick Start Guide](docs/QuickStart.md)

## Bugs and Feature Requests 
Let us know about bugs and feature requests through this repo's
[GitHub Issues](https://github.com/jmtyszka/bidskit/issues) page.

## Related Projects
- [heudiconv](https://github.com/nipy/heudiconv) General purpose heuristic DICOM converter
- [dcm2bids](https://github.com/cbedetti/Dcm2Bids) Christophe Beddetti's DICOM to BIDS converter 
