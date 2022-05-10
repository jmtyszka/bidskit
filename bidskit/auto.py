"""
Automatically build protocol translator from series descriptions and sequence parameters
in work/ conversion directory

MIT License
Copyright (c) 2017-2022 Mike Tyszka
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

from . import io as bio

def auto_translate(info, json_fname):

    ser_desc = info['SerDesc']

    suffices = {
        'func': ['bold', 'sbref'],
        'anat': ['T1w', 'T2w', 'PDw', 'T2starw', 'FLAIR',
                 'defacemask', 'MEGRE', 'MESE', 'VFA', 'IRT1',
                 'MP2RAGE', 'MPM', 'MTS', 'MTR'],
        'dwi': ['dwi']
    }

    # Use BIDS filename parser on ReproIn-style series description
    keys, _ = bio.parse_bids_fname(ser_desc)

    # Infer BIDS type directory
    bids_dir = 'anat'
    bids_stub = 'bold'
    bids_intendedfor = 'UNASSIGNED'

    return [bids_dir, bids_stub, bids_intendedfor]