# BIDSKIT Installation

BIDSKIT can be installed from GitHub source or from PyPI using the pip command

### Requirements
*bidskit* was developed for Python 3.7 and depends on several popular packages including *numpy* and *pydicom*.
Python dependencies are handled through setuptools (setup.py) during installation.

*bidskit* also requires that *dcm2nixx* version 1.0.20181124 or later.
See [Chris Rorden's GitHub repository](https://github.com/rordenlab/dcm2niix) for detailed installation instructions. 

### GitHub Installation

1. Clone this branch to your local system
   ```
   % git clone https://github.com/jmtyszka/bidskit.git
   ```
2. Install to your local Python 3 environment
   ```
   % cd bidskit
   % [sudo] python3 setup.py install
   ```
   
### PyPI Installation

1. Install the latest Python 3 version of *bidskit* from PyPI
    ```
    % [sudo] pip3 install bidskit
    ```