# BIDSKIT 2019.12.20
# MAINTAINER: jmt@caltech.edu

# Install Ubuntu 18.04 LTS Bionic Beaver
FROM ubuntu:bionic

# Install Node.js version 12
FROM node:12

# Install updates, Python3 for BIDS conversion script, Pip3 for Python to pull the pydicom module
# git and make for building DICOM convertor from source + related dependencies
# Clean up after to keep image size compact!
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y build-essential libjpeg-dev python3 python3-pip git cmake pkg-config pigz && \
    apt-get clean -y && \
    apt-get autoclean -y && \
    apt-get autoremove -y

# Install Node.js bids-validator
RUN npm install -g bids-validator

# Pull Chris Rorden's dcm2niix latest version from github and compile from source
# - dcm2niix is installed in /usr/local/bin within the container
# - not including support for JPEG2000 (optional -DUSE_OPENJPEG flag)
# - not including support for dcm2niibatch (optional -DBATCH_VERSION flag)
RUN cd /tmp && \
    git clone https://github.com/rordenlab/dcm2niix.git && \
    cd dcm2niix && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install

# Install important python3 packages explicitly to avoid compilation errors from setup.py
RUN pip3 install cython scipy numpy pandas

# Install python DICOM and BIDS packages
RUN pip3 install pydicom pybids

# Install python3 bidskit in the container
ADD . /myapp
WORKDIR /myapp
RUN python3 setup.py install
