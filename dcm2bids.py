#!/usr/bin/env python3
"""
Calculate Dice, Jaquard and related stats for inter and intra-observer labeling comparisons

Usage
----
dice.py <labelsA> <labelsB>
dice.py -h

Example
----
>>> dice.py labelsA.nii.gz labelsB.nii.gz

Authors
----
Mike Tyszka, Caltech Brain Imaging Center

Dates
----
2015-07-21 JMT From scratch

License
----
This file is part of atlaskit.

    atlaskit is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    atlaskit is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with atlaskit.  If not, see <http://www.gnu.org/licenses/>.

Copyright
----
2015 California Institute of Technology.
"""

__version__ = '0.2.0'

import sys
import argparse
import nibabel as nib
import numpy as np
import pandas as pd


def main():

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Dice, Jaccard and hausdorff_distance distances between labels')
    parser.add_argument('-a','--labelsA', required=True, help='Labeled volume A')
    parser.add_argument('-b','--labelsB', required=True, help='Labeled volume B')
    parser.add_argument('-k','--labelsKey', required=False, help='ITK-SNAP label key [optional]')
    parser.add_argument('-l','--labelsList', required=False, type=parse_range, help='List of label indices to process (eg 1-5, 7-9, 12)')

    # Parse command line arguments
    args = parser.parse_args()

    labelsA = args.labelsA
    labelsB = args.labelsB

    # Load labeled volumes
    A_nii, B_nii = nib.load(labelsA), nib.load(labelsB)
    A_labels, B_labels = A_nii.get_data(), B_nii.get_data()

    # Load and parse label key if provided
    if args.labelsKey:
        label_key = load_key(args.labelsKey)
    else:
        label_key = []

    # Limited list of labels to process
    if args.labelsList:
        unique_labels = args.labelsList
    else:
        unique_labels = np.unique(A_labels)

    # Voxel dimensions in mm (assume A and B have identical dimensions)
    vox_mm = np.array(A_nii.header.get_zooms())

    # Voxel volume in mm^3 (microliters) (from volume A)
    atlas_vox_vol_ul = vox_mm.prod()

    # Colume headers
    print('%24s,%8s,%8s,%8s,%10s,%10s,%10s,%10s,%10s' %
        ('Label', 'Index', 'nA', 'nB', 'vA_ul', 'vB_ul', 'Dice', 'Hausdorf', 'Jaccard'))


    # loop over each unique label value
    for label_idx in unique_labels:

        if label_idx > 0:

            # Find label name if provided
            if np.any(label_key):
                label_name = get_label_name(label_idx, label_key)
            else:
                label_name = 'Unknown'

            # Create label mask from A and B volumes
            A_mask = (A_labels == label_idx)
            B_mask = (B_labels == label_idx)

            # Count voxels in each mask
            nA, nB = np.sum(A_mask), np.sum(B_mask)

            # Only calculate stats if labels present in A or B
            if nA > 0 or nB > 0:

                # Find intersection and union of A and B masks
                AandB = np.logical_and(A_mask, B_mask)
                AorB = np.logical_or(A_mask, B_mask)

                # Count voxels in intersection and union
                nAandB, nAorB = np.sum(AandB), np.sum(AorB)

                # Similarity coefficients
                Jaccard = nAandB / float(nAorB)
                Dice = 2.0 * nAandB / float(nA + nB)

                # hausdorff_distance distance
                H = hausdorff_distance(A_mask, B_mask, vox_mm)

                # Absolute volumes of label in A and B
                A_vol_ul = np.sum(A_mask) * atlas_vox_vol_ul
                B_vol_ul = np.sum(B_mask) * atlas_vox_vol_ul

                if Dice < 0.001:
                    label_str = '>>> %20s' % label_name
                else:
                    label_str = label_name

                print('%24s,%8d,%8d,%8d,%10.3f,%10.3f,%10.3f,%10.3f,%10.3f' %
                    (label_str, label_idx, nA, nB, A_vol_ul, B_vol_ul, Dice, H, Jaccard))

    # Clean exit
    sys.exit(0)


def hausdorff_distance(A, B, vox_mm):
    """
    Calculate the hausdorff_distance distance in mm between two binary masks in 3D

    Parameters
    ----------
    A : 3D numpy array
        Binary mask A
    B : 3D numpy array
        Binary mask B
    vox_mm : numpy array
        voxel dimensions in mm

    Returns
    -------
    H : float
        hausdorff_distance distance between labels
    """

    # Create lists of all True points in both masks
    xA, yA, zA = np.nonzero(A)
    xB, yB, zB = np.nonzero(B)

    # Count elements in each point set
    nA = xA.size
    nB = xB.size

    if nA > 0 and nB > 0:

        # Init min dr to -1 for all points in A
        min_dr = -1.0 * np.ones([nA])

        for ac in range(0,nA):

            dx = (xA[ac] - xB[:]) * vox_mm[0]
            dy = (yA[ac] - yB[:]) * vox_mm[1]
            dz = (zA[ac] - zB[:]) * vox_mm[2]
            min_dr[ac] = np.min(np.sqrt(dx**2 + dy**2 + dz**2))

        # Find maximum over A of the minimum distances A to B
        H = np.max(min_dr)

    else:

        H = np.nan

    return H


def load_key(key_fname):
    '''
    Parse an ITK-SNAP label key file

    Parameters
    ----------
    key_fname

    Returns
    -------

    '''

    # Import key as a data table
    # Note the partially undocumented delim_whitespace flag
    data = pd.read_table(key_fname,
                         comment='#',
                         header=None,
                         names=['Index','R','G','B','A','Vis','Mesh','Name'],
                         delim_whitespace=True)

    return data


def get_label_name(label_idx, label_key):
    '''
    Search label key for label index and return name

    Parameters
    ----------
    label_idx
    label_key

    Returns
    -------

    '''

    label_name = 'Unknown Label'

    for i, idx in enumerate(label_key.Index):
        if label_idx == idx:
            label_name = label_key.Name[i]

    return label_name


def parse_range(astr):
    '''
    Parse compound list of integers and integer ranges

    Parameters
    ----------
    astr

    Returns
    -------

    '''
    result = set()
    for part in astr.split(','):
        x = part.split('-')
        result.update(range(int(x[0]), int(x[-1]) + 1))

    return sorted(result)


# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
    main()
