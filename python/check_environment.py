#! /usr/bin/env python
#
# Simple Check Environment - NO MAPNIK
#

import os,sys,math,urllib2,urllib
import psycopg2
import ppygis
from which import *
from urlparse import urlparse
#from xml.dom import minidom
import xml.etree.ElementTree as ET
from datetime import date, timedelta

import config
from osgeo import gdal
from osgeo import osr
from osgeo import ogr
from osgeo import gdal_array
from osgeo import gdalconst

import numpy
import scipy

version_num = int(gdal.VersionInfo('VERSION_NUM'))
if version_num < 1800: # because of GetGeoTransform(can_return_null)
	print('ERROR: Python bindings of GDAL 1.8.0 or later required')
	sys.exit(1)

err = which("convert")
if err == None:
	print "convert missing"
	sys.exit(-1)

err = which("bzip2")
if err == None:
	print "bzip2 missing"
	sys.exit(-1)

err = which("potrace")
if err == None:
	print "potrace missing"
	sys.exit(-1)

err = which("topojson")
if err == None:
	print "topojson missing"
	sys.exit(-1)

err = which("node")
if err == None:
	print "node missing"
	sys.exit(-1)
	
#
# Check Database Connection
#
def check_db(str):
	print "trying to connect to:", str
	
	connection 	= psycopg2.connect(str)
	cursor 		= connection.cursor()

	cmd = "SELECT version();"
	print cmd
	cursor.execute(cmd)
	result = cursor.fetchone()
	print result		
	connection.commit()
	cursor.close()
	connection.close()
	
envs = [
	"WORKSHOP_DIR",
	"DBHOST",
	"DBNAME",
	"DBOWNER",
	"DBPORT", 
	"PGPASS",
	"DATABASE_URL"
]

node_envs = [
    "FACEBOOK_APP_SECRET",
    "FACEBOOK_APP_ID",
    "FACEBOOK_PROFILE_ID",
    "TWITTER_SITE",
    "TWITTER_SITE_ID",
    "TWITTER_CREATOR",
    "TWITTER_CREATOR_ID",
    "TWITTER_DOMAIN",
    "COOKIEHASH"
]

environment = {}
	
for e in envs:
	print "checking:", e
	environment[e] = os.environ[e]
	assert (environment[e]), "Missing environment variable:"+e
	
print "All required environment variables are set..."

#
# Database Check
#

DATABASE_URL 	= os.environ["DATABASE_URL"]
assert( DATABASE_URL)
url 			= urlparse(DATABASE_URL)
dbhost			= url.hostname
dbport			= url.port
dbname			= url.path[1:]
user			= url.username
password		= url.password
		
str= "host=%s dbname=%s port=%s user=%s password=%s"% (dbhost,dbname,dbport,user,password)

print "Connect to", str
check_db(str)

# Check that Database ENVs match DATABASE_URL
if dbhost != os.environ["DBHOST"]:
	print "DBHOST does not match DATABASE_URL", dbhost, os.environ["DBHOST"], DATABASE_URL
	sys.exit(-1)

if dbport != int(os.environ["DBPORT"]):
	print "DBPORT does not match DATABASE_URL", dbport, os.environ["DBPORT"], DATABASE_URL
	sys.exit(-1)

if dbname != os.environ["DBNAME"]:
	print "DBNAME does not match DATABASE_URL", dbname, os.environ["DBNAME"], DATABASE_URL
	sys.exit(-1)

if user != os.environ["DBOWNER"]:
	print "DBOWNER does not match DATABASE_URL", user, os.environ["DBOWNER"], DATABASE_URL
	sys.exit(-1)

if password != os.environ["PGPASS"]:
	print "PGPASS does not match DATABASE_URL", password, os.environ["PGPASS"], DATABASE_URL
	sys.exit(-1)
	
	
print "Checking Node Environment for Publisher"
for e in node_envs:
	print "checking:", e
	environment[e] = os.environ[e]
	assert (environment[e]), "Missing environment variable:"+e

#
# Check Config Directories
#
# Simple ones only
#
config_dirs = [
	"DATA_DIR",
	"TRMM_DIR",
	"GEOS5_DIR",
	"GPM_DIR",
	"GFMS_DIR",
	"MODIS_ACTIVE_FIRES_DIR",
	"MODIS_BURNEDAREAS_DIR",
	"QUAKES_DIR",
	"LANDSLIDE_NOWCAST_DIR",
	"VHI_DIR"
]

for d in config_dirs:
	mydir = eval('config.'+d)
	if not os.path.exists(mydir):
		print "Directory:", mydir, " does not exist... you may need to create it"
	else:
		print mydir, " does  exist.  Good."
		

#
# Check if simple python processing scripts work for one region
#
today		= date.today()
dt			= today.strftime("%Y-%m-%d")
	
yesterday	= today - timedelta(1)
ydt			= yesterday.strftime("%Y-%m-%d")

dayAfterYesterday	= today - timedelta(2)
ydt2				= dayAfterYesterday.strftime("%Y-%m-%d")

#
# Make sure that region d02 is in defined in config.py
#

# Landslide nowcast
# python ./landslide_nowcast.py --region d02 --date 2015-09-23 -v

# TRMM data (already done in Landslide nowcast
# python ./trmm_process.py --region d02 --date 2015-09-23 -v

# Quakes from USGS
# python ./quake.py --region d02 --date 2015-09-23 -v

# MODIS BURNED AREAS from MODIS
# python ./modis-burnedareas.py --region d02 --date 2015-09-23 -v

# MODIS ACTIVE FIRES from MODIS  - PROBLEM with node
# python ./modis-active-fires.py --region d02 --date 2015-09-23 -v

# GPM Global, 1-d, 3-d and 7-d products
# python ./gpm_global.py  --date 2015-09-22 -v

# GEOS5 Global
# python ./geos5.py  --date 2015-09-23 -v

# GFMS Global
# python ./gfms_vectorizer.py  --date 2015-09-23 -v

# Vegetation Heath Index
# python ./vhi.py  --region d02 --date 2015-09-23 -v

