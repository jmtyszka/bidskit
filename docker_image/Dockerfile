# MAINTAINER: rnair@caltech.edu | feel free to copy and adapt as needed.
FROM ubuntu:trusty

# Install updates, Python3 for BIDS conversion script, Pip3 for Python to pull the pydicom module
# git and make for building DICOM convertor from source + related dependencies
# Clean up after to keep image size compact!
RUN apt-get update && apt-get upgrade -y && apt-get install -y build-essential libjpeg-dev python3 python3-pip git cmake pkg-config pigz && \
        apt-get clean -y && apt-get autoclean -y && apt-get autoremove -y

# Pull Chris Rorden's dcm2niix latest version from github and compile from source
# Not including support for JPEG2000(optional -DUSE_OPENJPEG flag) and optional -DBATCH_VERSION flag (for batch processing binary dcm2niibatch
# Include those flags with cmake, if required.
RUN cd /tmp && git clone https://github.com/rordenlab/dcm2niix.git && cd dcm2niix && mkdir build && \
        cd build && cmake .. && make && make install

#dcm2niix executable has been created on /usr/local/bin within the container

#Create a dir to store python script
RUN mkdir WORKDIR /app
COPY . /app

#Install required python depencendies (pydicom)
RUN pip3 install pydicom

#Create an entrypoint to pass ARGS to python script
ENTRYPOINT ["python3", "/app/dcm2bids.py"]

#That's all. Enjoy! 
