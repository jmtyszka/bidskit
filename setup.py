from setuptools import setup

setup(
    name = "bidskit",
    version = "1.2.0",
    author = "Mike Tyszka",
    author_email = "jmt@caltech.edu",
    description = ("DICOM to BIDS Converter"),
    long_description=("A tool for converting and organizing DICOM data in the BIDS format"),
    license = "MIT",
    keywords = "DICOM BIDS Converter",
    url = "http://packages.python.org/bidskit",
    packages=['bidskit', 'tests'],
    scripts=['bin/bidskit'],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: MIT License",
    ],

)