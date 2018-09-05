Installation
============

`getsentinel` can be installed via pip::
    
    pip install getsentinel

or from source @ https://www.bitbucket.org/wirrell/getsentinel

GDAL
----

You must install the Python GDAL bindings OSGeo separately.
It has been excluded from the requirements.txt as the current PyPI hosted
version does not work for all machines.

If you do not already have the GDAL C libraries installed, install them.

I recommended this method for installing C libraries and OSGeo from stackoverflow::

    sudo add-apt-repository -y ppa:ubuntugis/ppa
    sudo apt update 
    sudo apt install gdal-bin python-gdal python3-gdal

or similar for your Linux flavour.

from: https://stackoverflow.com/questions/37294127/python-gdal-2-1-installation-on-ubuntu-16-04
