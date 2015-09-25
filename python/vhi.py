#
# STAR - Global Vegetation Health Product
#
#
# Processes VHI Data for a specific region
# Notes: Data only comes once a week.  FTP is more likely to fail
#

import os, inspect, sys, math, urllib
import argparse

from datetime import date
from dateutil.parser import parse
from osgeo import gdal
import numpy
import json
from ftplib import FTP

import config

from browseimage import MakeBrowseImage 
from s3 import CopyToS3
#from level import CreateLevel

verbose 	= 0
force 		= 0
ftp_site 	= "ftp.star.nesdis.noaa.gov"
gis_path 	= "pub/corp/scsb/wguo/data/VHP_4km/geo_TIFF/"

def execute( cmd ):
	if verbose:
		print cmd
	os.system(cmd)

def get_files( gis_files, mydir):
	
	if verbose:
		print("Checking "+ftp_site+"/" + gis_path + "...")
	
	try:
		ftp = FTP(ftp_site)
	
		ftp.login()               					# user anonymous, passwd anonymous@
		ftp.cwd(gis_path)
	
	except Exception as e:
		print "FTP login Error", sys.exc_info()[0], e
		sys.exit(-1)

	for f in gis_files:
		print "Trying to download", f
		local_filename = os.path.join(mydir, f)
		if not os.path.exists(local_filename):
			if verbose:
				print "Downloading it...", f
			file = open(local_filename, 'wb')
			try:
				ftp.retrbinary("RETR " + f, file.write)
				file.close()
			except Exception as e:
				print "Weekly File not available:", sys.exc_info()[0], e					
				os.remove(local_filename)
				ftp.close();
				sys.exit(0)

	ftp.close()

def CreateLevel(maxl, minl, geojsonDir, fileName, src_ds, data, attr, _force, _verbose):
	force 				= _force
	verbose				= _verbose
	
	projection  		= src_ds.GetProjection()
	geotransform		= src_ds.GetGeoTransform()
	#band				= src_ds.GetRasterBand(1)
		
	xorg				= geotransform[0]
	yorg  				= geotransform[3]
	pres				= geotransform[1]
	xmax				= xorg + geotransform[1]* src_ds.RasterXSize
	ymax				= yorg - geotransform[1]* src_ds.RasterYSize
		
	driver 				= gdal.GetDriverByName( "GTiff" )

	dst_ds_dataset		= driver.Create( fileName, src_ds.RasterXSize, src_ds.RasterYSize, 1, gdal.GDT_Byte, [ 'COMPRESS=DEFLATE' ] )
	dst_ds_dataset.SetGeoTransform( geotransform )
	dst_ds_dataset.SetProjection( projection )
	o_band		 		= dst_ds_dataset.GetRasterBand(1)
	o_data				= o_band.ReadAsArray(0, 0, dst_ds_dataset.RasterXSize, dst_ds_dataset.RasterYSize )
	
	o_data.fill(255)
	o_data[data>=maxl] 	= 0
	o_data[data<minl]	= 0
	#o_data[data>0]		= 255

	count 				= (o_data > 0).sum()	

	if verbose:
		print "Level", minl, maxl, " count:", count

	if count > 0 :

		dst_ds_dataset.SetGeoTransform( geotransform )
			
		dst_ds_dataset.SetProjection( projection )
		
		o_band.WriteArray(o_data, 0, 0)
		
		ct = gdal.ColorTable()
		ct.SetColorEntry( 0, (255, 255, 255, 255) )
		ct.SetColorEntry( 255, (255, 0, 0, 255) )
		o_band.SetRasterColorTable(ct)
		
		dst_ds_dataset 	= None
		if verbose:
			print "Created", fileName

		cmd = "gdal_translate -q -of PNM " + fileName + " "+fileName+".pgm"
		execute(cmd)

		# -i  		invert before processing
		# -t 2  	suppress speckles of up to this many pixels. 
		# -a 1.5  	set the corner threshold parameter
		# -z black  specify how to resolve ambiguities in path decomposition. Must be one of black, white, right, left, minority, majority, or random. Default is minority
		# -x 		scaling factor
		# -L		left margin
		# -B		bottom margin

		cmd = str.format("potrace -i -z black -a 1.5 -t 3 -b geojson -o {0} {1} -x {2} -L {3} -B {4} ", fileName+".geojson", fileName+".pgm", pres, xorg, ymax ); 
		execute(cmd)
	
		cmd = str.format("topojson -o {0} --simplify-proportion 0.5 -p {3}={1} -- {3}={2}", fileName+".topojson", maxl, fileName+".geojson", attr ); 
		execute(cmd)
	
		# convert it back to json
		cmd = "topojson-geojson --precision 4 -o %s %s" % ( geojsonDir, fileName+".topojson" )
		execute(cmd)
	
		# rename file
		output_file = "%s_level_%d.geojson" % (attr, minl)
		json_file	= "%s.json" % attr
		cmd = "mv %s %s" % (os.path.join(geojsonDir,json_file), os.path.join(geojsonDir, output_file))
		execute(cmd)
		
		
def process(mydir, gis_file, r, region, s3_bucket, s3_folder, ymd ):

	# subset the file for that region
	bbox		= region['bbox']
	gis_file	= os.path.join(mydir, "..", gis_file)

	local_dir	= os.path.join(mydir, r)
	if not os.path.exists(local_dir):            
		os.makedirs(local_dir)
	
	subset_file	= os.path.join(local_dir, "vhi.%s.tif" % ymd)
	
	if force or not os.path.exists(subset_file):
		cmd = "gdalwarp -overwrite -q -te %f %f %f %f %s %s" % (bbox[0], bbox[1], bbox[2], bbox[3], gis_file, subset_file)
		execute(cmd)

	ds 					= gdal.Open( subset_file )
	geotransform		= ds.GetGeoTransform()
	px					= geotransform[1] / 10
	py					= geotransform[5] / 10
	ds					= None
	
	# upsample and convolve
	super_subset_file	= os.path.join(local_dir, "vhi_super.%s.tif" % ymd)
	cmd = "gdalwarp -overwrite -q -r cubicspline -tr %s %s -te %f %f %f %f -co COMPRESS=LZW %s %s" % (str(px), str(py), bbox[0], bbox[1], bbox[2], bbox[3], subset_file, super_subset_file)
	execute(cmd)

	geojsonDir	= os.path.join(local_dir, "geojson")
	if not os.path.exists(geojsonDir):            
		os.makedirs(geojsonDir)

	levelsDir	= os.path.join(local_dir,"levels")
	if not os.path.exists(levelsDir):            
		os.makedirs(levelsDir)

	merge_filename 		= os.path.join(geojsonDir, "vhi.%s.geojson" % ymd)
	topojson_filename 	= os.path.join(geojsonDir, "..", "vhi.%s.topojson" % ymd)
	browse_filename 	= os.path.join(geojsonDir, "..", "vhi.%s_browse.tif" % ymd)
	subset_filename 	= os.path.join(geojsonDir, "..", "vhi.%s_small_browse.tif" % ymd)
	osm_bg_image		= os.path.join(geojsonDir, "..", "osm_bg.png")
	sw_osm_image		= os.path.join(geojsonDir, "..", "vhi.%s_thn.jpg" % ymd)


	levels 				= [100, 84, 72, 60, 48, 36, 24, 12, 6, 0]
	
	# From http://colorbrewer2.org/
	hexColors 			= [ "#d53e4f", "#f46d43", "#fdae61", "#fee08b", "#ffffbf", "#e6f598", "#abdda4", "#66c2a5", "#3288bd"]
	
	ds 					= gdal.Open( super_subset_file )
	band				= ds.GetRasterBand(1)
	data				= band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize )
	
	data[data>100] = 0
	
	if force or not os.path.exists(topojson_filename+".gz"):
		for idx, l in enumerate(levels):
			print "level", idx
			if idx < len(levels)-1:
				fileName 		= os.path.join(levelsDir, ymd+"_level_%d.tif"%l)
				CreateLevel(l, levels[idx+1], geojsonDir, fileName, ds, data, "vhi", force, verbose)
			
		jsonDict = dict(type='FeatureCollection', features=[])
	
		for l in reversed(levels):
			fileName 		= os.path.join(geojsonDir, "vhi_level_%d.geojson"%l)
			if os.path.exists(fileName):
				print "merge", fileName
				with open(fileName) as data_file:    
					data = json.load(data_file)
		
				if 'features' in data:
					for f in data['features']:
						jsonDict['features'].append(f)
	

		with open(merge_filename, 'w') as outfile:
		    json.dump(jsonDict, outfile)	

		# Convert to topojson
		cmd 	= "topojson -p -o "+ topojson_filename + " " + merge_filename
		execute(cmd)

		cmd 	= "gzip --keep "+ topojson_filename
		execute(cmd)
		
	zoom = region['thn_zoom']
	if force or not os.path.exists(sw_osm_image):
		levels.pop()
		MakeBrowseImage(ds, browse_filename, subset_filename, osm_bg_image, sw_osm_image, levels, hexColors, force, verbose, zoom)
		
	ds = None
	
	file_list = [ sw_osm_image, topojson_filename, topojson_filename+".gz", subset_file ]
	
	CopyToS3( s3_bucket, s3_folder, file_list, force, verbose )
	
# ===============================
# Main
#
# python vhi.py --date 2015-03-27 -v -f

if __name__ == '__main__':

	aws_access_key 			= os.environ.get('AWS_ACCESSKEYID')
	aws_secret_access_key 	= os.environ.get('AWS_SECRETACCESSKEY')
	assert(aws_access_key)
	assert(aws_secret_access_key)
	
	parser = argparse.ArgumentParser(description='Generate VHI product')
	apg_input = parser.add_argument_group('Input')
	apg_input.add_argument("-f", "--force", action='store_true', help="HydroSHEDS forces new water image to be generated")
	apg_input.add_argument("-v", "--verbose", action='store_true', help="Verbose on/off")
	apg_input.add_argument("-d", "--date", help="Date 2015-03-20 or today if not defined")
	apg_input.add_argument("-r", "--region", help="region d02|d03")

	todaystr	= date.today().strftime("%Y-%m-%d")

	options 	= parser.parse_args()

	dt			= options.date or todaystr
	force		= options.force
	verbose		= options.verbose
	r			= options.region
	assert(config.regions[r])
	
	today		= parse(dt)
	year		= today.year
	month		= today.month
	day			= today.day
	weekday		= today.weekday()
	doy			= today.strftime('%j')
		
	week		= "%03d" % int(today.strftime("%U"))
	
	if verbose:
		print "Processing week", week
		
	ymd 		= "%d%02d%02d" % (year, month, day)		
	yweek		= "%d%s" % (year, week)
		
	gisdir		= os.path.join(config.data_dir, 'vhi',str(year))
	if not os.path.exists(gisdir):
	    os.makedirs(gisdir)

	mydir		= os.path.join(config.data_dir, 'vhi',str(year), doy)
	if not os.path.exists(mydir):
	    os.makedirs(mydir)
	
	region		= config.regions[r]
	s3_folder	= os.path.join("vhi", str(year), doy)
	s3_bucket	= region['bucket']

	gis_file	= "VHP.G04.C07.NP.P%s.VH.VHI.tif"%(yweek)
	
	if force or not os.path.exists(os.path.join(gisdir,gis_file)):
		get_files([gis_file], gisdir)
		process(mydir, gis_file, r, region, s3_bucket, s3_folder, ymd)
	else:
		print "VHI for week %s already done!" % week
