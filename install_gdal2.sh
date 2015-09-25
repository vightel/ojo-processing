#!/bin/env sh

cd /tmp && mkdir gdal2 && cd gdal2
wget http://download.osgeo.org/gdal/2.0.0/gdal-2.0.0.tar.gz
tar -xzvf gdal-2.0.0.tar.gz
rm gdal-2.0.0.tar.gz

cd /tmp/gdal2/gdal-2.0.0/
./configure --with-python --with-spatialite --with-pg --with-curl
make
make install
ldconfig
cd /tmp && rm -R *
exit