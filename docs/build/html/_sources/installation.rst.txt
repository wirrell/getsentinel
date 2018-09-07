Installation
============

`getsentinel` can be installed via pip::
    
    pip install getsentinel

or from source @ https://www.bitbucket.org/wirrell/getsentinel

GDAL
----
If you do not already have the GDAL C libraries installed, install them.
https://trac.osgeo.org/gdal/wiki/DownloadSource

Note
----
Currenlty the latest version of GDAL does not compile on some systems.

`sudo yum install gdal` will install GDAL 2.2.4.

when you have installed the GDAL libraries, type `gdalconfig --version` to get
the version number of your GDAL installation.

From there you should `pip install pygdal=={yourgdalversionnumber}` to ensure
you get a working pygdal installation.

Because this is a nuanced pygdal installation, pygdal is not currently included
in the `pip` required packages for `getsentinel`.
