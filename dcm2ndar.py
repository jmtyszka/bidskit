#!/usr/bin/env python3
"""
Convert flat DICOM file set into an NDAR-compliant fileset

Usage
----
dcm2ndar.py -i <DICOM Directory> -o <NDAR Directory>

Example
----
% dcm2ndar.py -i sub-001 -o sub-001.ndar

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2016-08-09 JMT Adapt from dcm2bids.py

MIT License

Copyright (c) 2016 Mike Tyszka

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__version__ = '0.1.0'

import os
import sys
import argparse
import subprocess
import pydicom
import json
import glob
import shutil
import nibabel as nib
from datetime import datetime
from dateutil import relativedelta


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Convert DICOM files to NDAR-compliant fileset')
    parser.add_argument('-i', '--indir', required=True, help='Source directory containing subject DICOM directories')
    parser.add_argument('-o', '--outdir', required=False, help='Output directory for subject NDAR directories')

    # Parse command line arguments
    args = parser.parse_args()

    dcm_root_dir = args.indir

    if args.outdir:
        ndar_root_dir = args.outdir
    else:
        ndar_root_dir = args.indir + '.ndar'

    # Load protocol translation and exclusion info from DICOM directory
    # If no translator is present, prot_dict is an empty dictionary
    # and a template will be created in the DICOM directory. This template should be
    # completed by the user and the conversion rerun.
    prot_dict_json = os.path.join(dcm_root_dir, 'Protocol_Translator.json')
    prot_dict = ndar_load_prot_dict(prot_dict_json)

    # Set flag to write template protocol translator to DICOM directory
    create_prot_dict = True
    if prot_dict:
        create_prot_dict = False

    # Safe create output NDAR root directory
    if os.path.isdir(ndar_root_dir):
        shutil.rmtree(ndar_root_dir)
    os.makedirs(ndar_root_dir)

    # Loop over each subject's DICOM directory within the root source directory
    for SID in os.listdir(dcm_root_dir):

        dcm_sub_dir = os.path.join(dcm_root_dir, SID)

        # Only process subdirectories
        if os.path.isdir(dcm_sub_dir):

            print('Processing subject ' + SID)

            # Create subject directory
            print('  Creating NDAR subject directory')
            ndar_sub_dir = os.path.join(ndar_root_dir, SID)
            subprocess.call(['mkdir', '-p', ndar_sub_dir])

            # Create NDAR summary CSV for this subject
            ndar_csv_fname = os.path.join(ndar_sub_dir, SID + '_NDAR.csv')
            ndar_csv_fd = ndar_init_summary(ndar_csv_fname)

            # Read additional subject-level DICOM header fields from first DICOM image
            dcm_info = ndar_dcm_info(dcm_sub_dir)

            # Run dcm2niix conversion from DICOM to Nifti with BIDS sidecars for metadata
            # This relies on the current CBIC branch of dcm2niix which extracts additional DICOM fields
            # required by NDAR
            subprocess.call(['dcm2niix', '-b', 'y', '-f', 'sub-%n_%p', '-o', ndar_sub_dir, dcm_sub_dir])

            # Loop over all Nifti files (*.nii, *.nii.gz) for this SID
            # glob returns the full relative path from the NDAR root dir
            for nii_fname_full in glob.glob(os.path.join(ndar_sub_dir, '*.nii*')):

                # Read Nifti header for image FOV, extent (ie matrix) and voxel dimensions
                print('  Reading Nifti header')
                nii_info = ndar_nifti_info(nii_fname_full)

                # Isolate base filename
                nii_fname = os.path.basename(nii_fname_full)

                # Parse file basename
                SID, prot, fstub = ndar_parse_filename(nii_fname)

                # Full path for file stub
                fstub_full = os.path.join(ndar_sub_dir, fstub)

                # Check if we're creating new protocol dictionary
                if create_prot_dict:

                    print('  Adding protocol %s to dictionary' % prot)

                    # Add current protocol to protocol dictionary
                    # The value defaults to "EXCLUDE" which should be replaced with the correct NDAR
                    # ImageDescription for this protocol (eg "T1w Structural", "BOLD MB EPI Resting State")
                    prot_dict[prot] = "EXCLUDE"

                else:

                    # JSON sidecar for this image
                    json_fname = fstub_full + '.json'
                    if not os.path.isfile(json_fname):
                        print('* JSON sidecar not found')
                        break

                    # Skip excluded protocols
                    if prot_dict[prot] == 'EXCLUDE':

                        print('* Excluding protocol ' + prot)

                        # Remove all files related to this protocol
                        for f in glob.glob(fstub_full + '.*'):
                            os.remove(f)

                    else:

                        print('  Converting protocol ' + prot)

                        # Read JSON sidecar contents
                        json_fd = open(json_fname, 'r')
                        info = json.load(json_fd)
                        json_fd.close()

                        # Combine JSON, Nifti and DICOM info dictionaries
                        info.update(nii_info)
                        info.update(dcm_info)

                        # Add remaining fields not in JSON or DICOM metadata
                        info['SID'] = SID
                        info['ImageFile'] = os.path.basename(nii_fname)
                        info['ImageDescription'] = prot_dict[prot]
                        info['ScanType'] = ndar_scantype(prot_dict[prot])
                        info['Orientation'] = ndar_orientation(info)

                        # Add row to NDAR summary CSV file
                        ndar_add_row(ndar_csv_fd, info)

                        # Delete JSON file
                        os.remove(json_fname)


            # Close NDAR summary file for this subject
            ndar_close_summary(ndar_csv_fd)

    # Create combined protocol translator in DICOM root directory if necessary
    if create_prot_dict:
        ndar_create_prot_dict(prot_dict_json, prot_dict)

    # Clean exit
    sys.exit(0)


def ndar_load_prot_dict(prot_dict_json):
    '''
    Read protocol translations from JSON file
    :param prot_dict_json:
    :return:
    '''

    if os.path.isfile(prot_dict_json):

        # Read JSON protocol translator
        json_fd = open(prot_dict_json, 'r')
        prot_trans = json.load(json_fd)
        json_fd.close()

    else:

        print('* Protocol translator missing')
        print('* Creating template translator in %s' % prot_dict_json)

        # Initialize empty dictionary to be filled during subsequent file loop
        prot_trans = dict()

    return prot_trans


def ndar_create_prot_dict(prot_dict_json, prot_dict):
    '''
    Write protocol translation dictionary template to JSON file
    :param prot_dict_json:
    :param prot_dict:
    :return:
    '''
    json_fd = open(prot_dict_json, 'w')
    json.dump(prot_dict, json_fd, indent=4, separators=(',', ':'))
    json_fd.close()

    print('')
    print('---')
    print('New protocol dictionary created : %s' % prot_dict_json)
    print('Remember to replace "EXCLUDE" values in dictionary with an appropriate image description')
    print('For example "MP-RAGE T1w 3D structural" or "MB-EPI BOLD resting-state')
    print('---')
    print('')

    return


def ndar_parse_filename(fname):
    """
    Extract SID and protocol string from filename in the form sub-<SID>_<Protocol String>.[nii or nii.gz]
    
    :param fname:
    :return: SID, prot, fstub
    """

    # Init return values
    SID, prot, fstub = 'None', 'None', 'None'

    # Strip .nii or .nii.gz from fname
    fstub = fname.replace('.nii.gz','').replace('.nii','')

    # Split stub at first underscore
    for chunk in fstub.split('_', 1):
        if chunk.startswith('sub-'):
            # SID is everything after "sub-" in this chunk
            _, SID = chunk.split('sub-', 1)
        else:
            prot = chunk

    return SID, prot, fstub


def ndar_scantype(desc):
    """
    Best effort guess at scan type from description

    NDAR allowed MRI scan_type values
    ----
    fMRI
    MR structural (T1)
    MR structural (T2)
    MR structural (PD)
    MR structural (FSPGR);
    MR structural (MPRAGE)
    MR structural (PD, T2)
    MR structural (B0 map)
    MR structural (B1 map);
    Field Map
    MR diffusion
    single-shell DTI
    multi-shell DTI
    ASL

    :param desc:
    :return scan_type:
    """

    # Convert description to upper case
    desc = desc.upper()

    # Search for common contrasts
    if 'T1' in desc:
        scan_type = 'MR structural (T1)'
    elif 'T2' in desc:
        scan_type = 'MR structural (T2)'
    elif 'FIELDMAP' in desc or 'FMAP' in desc or 'FIELD MAP' in desc or 'B0' in desc:
        scan_type = 'MR structural (B0 map)'
    elif 'BOLD' in desc:
        scan_type = 'fMRI'
    else:
        scan_type = 'MR structural (T1)' # T1 structural fallback value

    return scan_type


def ndar_orientation(info):

    orientation = 'Axial'

    if 'spc3d' in info['PulseSequenceDetails']:
        orientation = 'Sagittal'

    if 'tfl3d' in info['PulseSequenceDetails']:
        orientation = 'Sagittal'

    return orientation


def ndar_nifti_info(nii_fname):
    '''
    Extract Nifti header fields not handled by dcm2niix
    :param nii_fname: Nifti image filename
    :return: nii_info: Nifti information dictionary
    '''

    # Init a new dictionary
    nii_info = dict()

    # Load Nifti header
    nii = nib.load(nii_fname)
    hdr = nii.header

    dim = hdr['dim']
    res = hdr['pixdim']

    # Fill dictionary
    nii_info['AcquisitionMatrix'] = '%dx%d' % (dim[1], dim[2])
    nii_info['NDims'] = dim[0]
    nii_info['ImageExtent1'] = dim[1]
    nii_info['ImageExtent2'] = dim[2]
    nii_info['ImageExtent3'] = dim[3]
    nii_info['ImageExtent4'] = dim[4]
    nii_info['ImageExtent5'] = dim[5]
    nii_info['ImageResolution1'] = res[1]
    nii_info['ImageResolution2'] = res[2]
    nii_info['ImageResolution3'] = res[3]
    nii_info['ImageResolution4'] = res[4]
    nii_info['ImageResolution5'] = res[5]

    # Use z dimension voxel spacing as slice thickness
    nii_info['SliceThickness'] = dim[3]

    if dim[0] > 3:
        nii_info['Extent4Type'] = 'Timeseries'
    else:
        nii_info['Extent4Type'] = 'None'

    return nii_info


def ndar_dcm_info(dcm_dir):
    """
    Extract additional subject-level DICOM header fields not handled by dcm2niix
    from first DICOM image in directory    
    
    :param dcm_dir: DICOM directory containing subject files
    :return: dcm_info: extra information dictionary
    """

    # Loop over files until first valid DICOM is found
    ds = []
    for dcm in os.listdir(dcm_dir):
        try:
            ds = pydicom.read_file(os.path.join(dcm_dir, dcm))
        except:
            pass

        # Break out if valid DICOM read
        if ds:
            break

    # Init a new dictionary
    dcm_info = dict()

    # Read DoB and scan date
    dob = ds.PatientBirthDate
    scan_date = ds.AcquisitionDate

    # Calculate age in months at time of scan using datetime functions
    d1 = datetime.strptime(dob, '%Y%M%d')
    d2 = datetime.strptime(scan_date, '%Y%M%d')
    rd = relativedelta.relativedelta(d2, d1)

    # Approximation since residual day to month conversion assumes 1 month = 30 days
    age_months = rd.years * 12 + rd.months + round(rd.days / 30.0)

    # Fill dictionary
    dcm_info['Sex'] = ds.PatientSex
    dcm_info['PatientPosition'] = ds.PatientPosition
    dcm_info['TransmitCoil'] = ds.TransmitCoilName
    dcm_info['SoftwareVersions'] = ds.SoftwareVersions
    dcm_info['PhotometricInterpretation'] = ds.PhotometricInterpretation
    dcm_info['AgeMonths'] = age_months
    dcm_info['ScanDate'] = datetime.strftime(d2, '%M/%d/%Y') # NDAR scan date format MM/DD/YYYY

    return dcm_info


def ndar_init_summary(fname):
    '''
    Open a summary CSV file and initialize with NDAR Image03 preamble
    :param fname:
    :return:
    '''

    # Write NDAR Image03 preamble and column headers
    ndar_fd = open(fname, 'w')
    ndar_fd.write('"image","03"\n')
    ndar_fd.write('"subjectkey","src_subject_id","interview_date","interview_age","gender","comments_misc",')
    ndar_fd.write('"image_file","image_thumbnail_file","image_description","experiment_id","scan_type","scan_object",')
    ndar_fd.write('"image_file_format","data_file2","data_file2_type","image_modality","scanner_manufacturer_pd",')
    ndar_fd.write('"scanner_type_pd","scanner_software_versions_pd","magnetic_field_strength",')
    ndar_fd.write('"mri_repetition_time_pd","mri_echo_time_pd","flip_angle","acquisition_matrix",')
    ndar_fd.write('"mri_field_of_view_pd","patient_position","photomet_interpret",')
    ndar_fd.write('"receive_coil","transmit_coil","transformation_performed","transformation_type","image_history",')
    ndar_fd.write('"image_num_dimensions","image_extent1","image_extent2","image_extent3",')
    ndar_fd.write('"image_extent4","extent4_type","image_extent5","extent5_type",')
    ndar_fd.write('"image_unit1","image_unit2","image_unit3","image_unit4","image_unit5",')
    ndar_fd.write('"image_resolution1","image_resolution2","image_resolution3","image_resolution4",')
    ndar_fd.write('"image_resolution5","image_slice_thickness","image_orientation",')
    ndar_fd.write('"qc_outcome","qc_description","qc_fail_quest_reason","decay_correction","frame_end_times",')
    ndar_fd.write('"frame_end_unit","frame_start_times","frame_start_unit","pet_isotope","pet_tracer",')
    ndar_fd.write('"time_diff_inject_to_image","time_diff_units","pulse_seq","slice_acquisition","software_preproc",')
    ndar_fd.write('"study","week","experiment_description","visit","slice_timing",')
    ndar_fd.write('"bvek_bval_files","bvecfile","bvalfile"')

    # Final newline
    ndar_fd.write('\n')

    return ndar_fd


def ndar_close_summary(fd):
    fd.close()
    return


def ndar_add_row(fd, info):
    """
    Write a single experiment row to the NDAR summary CSV file
    :param fd:
    :param info:
    :return:
    """

    # Field descriptions for NDAR Image03 MRI experiments
    # ElementName, DataType, Size, Required, ElementDescription, ValueRange, Notes, Aliases

    # subjectkey,GUID,,Required,The NDAR Global Unique Identifier (GUID) for research subject,NDAR*,,
    fd.write('"TBD",')

    # src_subject_id,String,20,Required,Subject ID how it's defined in lab/project,,,
    fd.write('"%s",' % info.get('SID','Unknown'))

    # interview_date,Date,,Required,Date on which the interview/genetic test/sampling/imaging was completed. MM/DD/YYYY,,Required field,ScanDate
    fd.write('"%s",' % info.get('ScanDate','Unknown'))

    # interview_age,Integer,,Required,Age in months at the time of the interview/test/sampling/imaging.,0 :: 1260,
    # "Age is rounded to chronological month. If the research participant is 15-days-old at time of interview,
    # the appropriate value would be 0 months. If the participant is 16-days-old, the value would be 1 month.",
    fd.write('%d,' % info.get('AgeMonths','Unknown'))

    # gender,String,20,Required,Sex of the subject,M;F,M = Male; F = Female,
    fd.write('"%s",' % info.get('Sex','Unknown'))

    # comments_misc
    fd.write('"",')

    # image_file,File,,Required,"Data file (image, behavioral, anatomical, etc)",,,file_source
    fd.write('"%s",' % info.get('ImageFile','Unknown'))

    # image_thumbnail_file
    fd.write('"",')

    # Image description and scan type overlap strongly (eg fMRI), so we'll use the translated description provided
    # by the user in the protocol dictionary for both NDAR fields. The user description should provide information
    # about both the sequence type used (eg MB-EPI or MP-RAGE) and the purpose of the scan (BOLD resting-state,
    # T1w structural, B0 fieldmap phase).
    # Note the 50 character limit for scan type.

    # image_description,String,512,Required,"Image description, i.e. DTI, fMRI, Fast SPGR, phantom, EEG, dynamic PET",,,
    fd.write('"%s",' % info.get('ImageDescription','Unknown'))

    # experiment_id,Integer,,Conditional,ID for the Experiment/settings/run,,,
    fd.write('"",')

    # scan_type,String,50,Required,Type of Scan,
    # "MR diffusion; fMRI; MR structural (MPRAGE); MR structural (T1); MR structural (PD); MR structural (FSPGR);
    # MR structural (T2); PET; ASL; microscopy; MR structural (PD, T2); MR structural (B0 map); MR structural (B1 map);
    # single-shell DTI; multi-shell DTI; Field Map; X-Ray",,
    fd.write('"%s",' % info.get('ScanType'))

    # scan_object,String,50,Required,"The Object of the Scan (e.g. Live, Post-mortem, or Phantom",Live; Post-mortem; Phantom,,
    fd.write('"Live",')

    # image_file_format,String,50,Required,Image file format,
    # AFNI; ANALYZE; AVI; BIORAD; BMP; BRIK; BRUKER; CHESHIRE; COR; DICOM; DM3; FITS; GE GENESIS; GE SIGNA4X; GIF;
    # HEAD; ICO; ICS; INTERFILE; JPEG; LSM; MAGNETOM VISION; MEDIVISION; MGH; MICRO CAT; MINC; MIPAV XML; MRC; NIFTI;
    # NRRD; OSM; PCX; PIC; PICT; PNG; QT; RAW; SPM; STK; TIFF; TGA; TMG; XBM; XPM; PARREC; MINC HDF; LIFF; BFLOAT;
    # SIEMENS TEXT; ZVI; JP2; MATLAB; VISTA; ecat6; ecat7;,,
    fd.write('"NIFTI",')

    # data_file2
    fd.write('"",')

    # data_file2_type
    fd.write('"",')

    # image_modality,String,20,Required,Image modality, MRI;
    fd.write('"MRI",')

    # scanner_manufacturer_pd,String,30,Conditional,Scanner Manufacturer,,,
    fd.write('"%s",' % info.get('Manufacturer','Unknown'))

    # scanner_type_pd,String,50,Conditional,Scanner Type,,,ScannerID
    fd.write('"%s",' % info.get('ManufacturersModelName','Unknown'))

    # scanner_software_versions_pd
    fd.write('"%s",' % info.get('SoftwareVersions','Unknown'))

    # magnetic_field_strength,String,50,Conditional,Magnetic field strength,,,
    fd.write('%f,' % info.get('MagneticFieldStrength','Unknown'))

    # mri_repetition_time_pd,Float,,Conditional,Repetition Time (seconds),,,
    fd.write('%0.4f,' % info.get('RepetitionTime',-1.0))

    # mri_echo_time_pd,Float,,Conditional,Echo Time (seconds),,,
    fd.write('%0.4f,' % info.get('EchoTime',-1.0))

    # flip_angle,String,30,Conditional,Flip angle,,,
    fd.write('%0.1f,' % info.get('FlipAngle',-1.0))

    # MRI conditional fields
    fd.write('"%s",' % info.get('AcquisitionMatrix'))  # acquisition_matrix
    fd.write('"%s",' % info.get('FOV'))  # mri_field_of_view_pd
    fd.write('"%s",' % info.get('PatientPosition'))  # patient_position
    fd.write('"%s",' % info.get('PhotometricInterpretation'))  # photomet_interpret
    fd.write('"",')  # receive_coil
    fd.write('"%s",' % info.get('TransmitCoil'))  # transmit_coil
    fd.write('"No",')  # transformation_performed
    fd.write('"",')  # transformation_type
    fd.write('"",')  # image_history
    fd.write('%d,' % info.get('NDims'))  # image_num_dimensions
    fd.write('%d,' % info.get('ImageExtent1'))  # image_extent1
    fd.write('%d,' % info.get('ImageExtent2'))  # image_extent2
    fd.write('%d,' % info.get('ImageExtent3'))  # image_extent3
    fd.write('%d,' % info.get('ImageExtent4'))  # image_extent4
    fd.write('"%s",' % info.get('Extent4Type'))  # extent4_type
    fd.write('"",')  # image_extent5
    fd.write('"",')  # extent5_type
    fd.write('"Millimeters",')  # image_unit1
    fd.write('"Millimeters",')  # image_unit2
    fd.write('"Millimeters",')  # image_unit3
    fd.write('"Seconds",')  # image_unit4
    fd.write('"",')  # image_unit5
    fd.write('%0.3f,' % info.get('ImageResolution1'))  # image_resolution1
    fd.write('%0.3f,' % info.get('ImageResolution2'))  # image_resolution2
    fd.write('%0.3f,' % info.get('ImageResolution3'))  # image_resolution3
    fd.write('%0.3f,' % info.get('ImageResolution4'))  # image_resolution4
    fd.write('%0.3f,' % info.get('ImageResolution5'))  # image_resolution5
    fd.write('%0.3f,' % info.get('SliceThickness'))  # image_slice_thickness
    fd.write('"%s",' % info.get('Orientation'))  # image_orientation
    fd.write('"",')  # qc_outcome
    fd.write('"",')  # qc_description
    fd.write('"",')  # qc_fail_quest_reason
    fd.write('"",')  # decay_correction
    fd.write('"",')  # frame_end_times
    fd.write('"",')  # frame_end_unit
    fd.write('"",')  # frame_start_times
    fd.write('"",')  # frame_start_unit
    fd.write('"",')  # pet_isotope
    fd.write('"",')  # pet_tracer
    fd.write('"",')  # time_diff_inject_to_image
    fd.write('"",')  # time_diff_units
    fd.write('"",')  # pulse_seq
    fd.write('"",')  # slice_acquisition
    fd.write('"None",')  # software_preproc
    fd.write('"",')  # study
    fd.write('"",')  # week
    fd.write('"",')  # experiment_description
    fd.write('"",')  # visit
    fd.write('"%s",' % str(info.get('SliceTiming')))  # slice_timing
    fd.write('"",')  # bvek_bval_files
    fd.write('"",')  # bvecfile
    fd.write('"",')  # bvalfile

    # Final newline
    fd.write('\n')

    return


def strip_extensions(fname):
    fstub, fext = os.path.splitext(fname)
    if fext == '.gz':
        fstub, fext = os.path.splitext(fstub)
    return fstub


def ndar_include_prot(prot, prot_excludes):
    '''
    Returns False if protocol is in exclude list
    :param prot:
    :param prot_excludes:
    :return:
    '''

    status = True
    for pe in prot_excludes:
        if pe in prot:
            status = False

    return status

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
