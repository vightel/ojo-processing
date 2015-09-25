##
# ojo/processing
#
# Pat Cappelaere, Vightel Corporation
#
# GDAL 2.0.0
# Node.js v.0.12.2
# 

# Ubuntu 14.04 Trusty Tahyr
FROM ubuntu:trusty

MAINTAINER Pat Cappelaere <pat@cappelaere.com>

# Install basic dependencies
RUN apt-get update -y && apt-get install -y \
    software-properties-common \
    python-software-properties \
    build-essential \
	python-dev \
    python-numpy \
    libspatialite-dev \
    sqlite3 \
    libpq-dev \
    libcurl4-gnutls-dev \
	libtiff5-dev \
    libproj-dev \
    libxml2-dev \
    libgeos-dev \
    libnetcdf-dev \
    libpoppler-dev \
    libspatialite-dev \
    libhdf4-alt-dev \
    libhdf5-serial-dev \
    wget unzip zip

# Get GDAL, Compile and install
ADD ./install_gdal2.sh /tmp/
RUN sh /tmp/install_gdal2.sh

# Potrace
RUN apt-get install -y potrace

# Imagemagick
RUN apt-get install -y imagemagick

RUN apt-get install -y curl git git-core

# Node
RUN curl -sL https://deb.nodesource.com/setup_0.12 | bash -
RUN apt-get install -y nodejs
RUN npm -g install topojson nodemon foreman

# Install Python libraries
RUN apt-get install -y python-pip python-numpy python-scipy python-nose python-psycopg2 python-dateutil python-argparse python-boto python-grib python-pyproj
RUN pip install PPyGIS

# Install Pytrmm
COPY ./pytrmm-0.1.0.tar.gz /tmp/pytrmm-0.1.0.tar.gz
RUN cd /tmp \
	&& tar -xzvf pytrmm-0.1.0.tar.gz \
	&& cd pytrmm-0.1.0 \
	&& python setup.py install


# NOTE: you may have to tweak if you use another target platform than Heroku
#
# copy env file and add a source instruction to .bash_profile
# this will be execute when we login (as root)
COPY ./envs.docker.sh /root/envs.docker.sh
COPY ./bash_profile /root/.bash_profile
 
# Only one command suggested when issuing a run
