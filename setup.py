#!/usr/bin/python
# vim: set sw=4 sts=4 et tw=120 :

from setuptools import setup, find_packages

with open('syncrm/_version.py') as f:
    exec(f.read())

setup(name='syncrm',
    version=__version__,
    author='Danny van Dyk',
    author_email='danny.van.dyk@gmail.com',
    url='https://github.com/dvandyk/syncrm',
    description='Toolkit to synchronize with the reMarkable eInk tablet',
    license='LGPLv2',
    packages=find_packages(),
    package_data={
        'syncrm': [],
    },
    install_requires=[ 'FileLock', 'py-dateutil', 'svglib', 'PyPDF2' ],
    extras_require={
        'testing': [],
    },
    entry_points={
        'console_scripts': [ 'syncrm = syncrm.cli:syncrm_cli' ],
    },
)
