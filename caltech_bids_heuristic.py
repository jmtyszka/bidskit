"""
Caltech-specific DICOM to BIDS conversion heuristic

AUTHOR: Mike Tyszka
PLACE: Caltech
DATES: 2017-04-05 JMT Adapted from the cmrr_bids.py heuristic provided by heudiconv package 
"""

import os


def create_key(template, outtype=('nii.gz',), annotation_classes=None):

    if template is None or not template:
        raise ValueError('Template must be a valid format string')

    return template, outtype, annotation_classes


def infotodict(seqinfo):
    """
    Heuristic evaluator for determining which runs belong where
    allowed template fields - follow python string module: 
    
    item: index within category 
    subject: participant id 
    seqitem: run number during scanning
    subindex: sub index within group
    session: scan index for longitudinal acq
    """

    # Optional full seqinfo output
    # print(seqinfo)

    # Optional DICOM subdirectory creation
    # and_dicom = ('dicom', 'nii.gz')
    # eg t1 = create_key('{session}/anat/sub-{subject}_T1w', outtype=and_dicom)

    t1 = create_key('anat/sub-{subject}_run-{item:02d}_T1w')
    t2 = create_key('anat/sub-{subject}_run-{item:02d}_T2w')
    rsbold = create_key('func/sub-{subject}_task-rest_run-{item:02d}_bold')
    loi1 = create_key('func/sub-{subject}_task-LOI1_bold')
    loi2 = create_key('func/sub-{subject}_task-LOI2_bold')
    fmap_rsbold = create_key('fmap/sub-{subject}_acq-rest_{purpose}')
    fmap_loi = create_key('fmap/sub-{subject}_acq-LOI_{purpose}')

    # Init returned info structure
    info = { t1: [], t2: [],
             rsbold: [], loi1:[], loi2:[],
             fmap_rsbold: [], fmap_loi: [] }

    for idx, s in enumerate(seqinfo):

        # Extract some common fields from the seqinfo record
        nx, ny, nz, nt = s[6], s[7], s[8], s[9]
        ser_no, prot_name, im_type = s[2], s[12], s[19]

        mag_phs = im_type[2]

        # Structurals
        if ('T1' in prot_name):
            info[t1].append({'item':ser_no})
        elif ('T2' in prot_name):
            info[t2].append({'item':ser_no})

        # fMRI
        elif ('rsBOLD' in prot_name) and (nt > 300):
            info[rsbold].append({'item':ser_no})
        elif ('LOI_1' in prot_name) and (nt > 300):
            info[loi1].append([ser_no])
        elif ('LOI_2' in prot_name) and (nt > 300):
            info[loi2].append([ser_no])

        # Fieldmaps
        elif ('Fieldmap_rsBOLD' in prot_name):
            if 'M' in mag_phs:
                info[fmap_rsbold].append({'item':ser_no, 'purpose':'fmapmag'})
            else:
                info[fmap_rsbold].append({'item': ser_no, 'purpose': 'fmapphs'})
        elif ('Fieldmap_LOI' in prot_name):
            if 'M' in mag_phs:
                info[fmap_loi].append({'item':ser_no, 'purpose':'fmapmag'})
            else:
                info[fmap_loi].append({'item': ser_no, 'purpose': 'fmapphs'})

        else:
            pass

    return info
