# BIDSKIT Installation

BIDSKIT can be installed from GitHub source or from PyPI using the pip command

### Requirements
*bidskit* was developed for Python 3.7 and depends on several popular packages including *numpy* and *pydicom*.
Python dependencies are handled through setuptools (setup.py) during installation.

#### dcm2niix
*bidskit* also requires that *dcm2nixx* version 1.0.20181125 or later.
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
    

### Optional Extensions
#### bids-validator
We recommend installing the Node.js application [bids-validator](https://github.com/bids-standard/bids-validator)
for post-conversion validation from within *bidskit*.

1. Install [Node.js](https://nodejs.org/en/) (version 8.0 or later)
2. Install *bids-validator*
    ```
    % npm install -g bids-validator
    ```  