#!/usr/bin/env python
#
# Created on 11/21/2013 Pat Cappelaere - Vightel Corporation
#
# Generates 24hr Forecast Landslide Estimate
#

import numpy, sys, os, inspect, urllib
import argparse

from osgeo import osr, gdal
from ftplib import FTP
import datetime
from datetime import date, timedelta
from which import *
from dateutil.parser import parse

import json

from browseimage import MakeBrowseImage 
from s3 import CopyToS3
from level import CreateLevel

# Site configuration
import config

force 		= 0
verbose 	= 0

def execute(cmd):
	if(verbose):
		print cmd
	os.system(cmd)
	
def save_tiff(dx, data, fname, ds):
	fullName 	= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, fname+".tif")
	driver 		= gdal.GetDriverByName("GTiff")
	
	out_ds 		= driver.CreateCopy(fullName, ds, 0)
	band		= out_ds.GetRasterBand(1)
	band.WriteArray(data, 0, 0)
	ct = gdal.ColorTable()
	ct.SetColorEntry( 0, (0, 0, 0, 0) )
	ct.SetColorEntry( 1, (255, 0, 0, 255) )
	ct.SetColorEntry( 127, (255, 255, 0, 255) )
	band.SetRasterColorTable(ct)
	
	out_ds	= None
	
	if verbose:
		print "Created", fullName
		
# Generate Current
def build_tif(dx, region, dir, date):
	region 		= config.regions[dx]
	bbox		= region['bbox']
	tzoom   	= region['tiles-zoom']
	pixelsize   = region['pixelsize']
	thn_width   = region['thn_width']
	thn_height  = region['thn_height']
	bucketName 	= region['bucket']

	# get the low percentile rainfall limits
	limit_low = os.path.join(config.data_dir,"ant_r", "%s_50r.tif" % (dx))
	if not os.path.exists(limit_low):
		print "**ERR: file not found", limit_low
		sys.exit(-1)

	# get the high percentile rainfall limits
	limit_high = os.path.join(config.data_dir,"ant_r", "%s_90r.tif" % (dx))
	if not os.path.exists(limit_high):
		print "**ERR: file not found", limit_high
		sys.exit(-1)

	# get the vhigh percentile rainfall limits
	limit_vhigh = os.path.join(config.data_dir,"ant_r", "%s_95r.tif" % (dx))
	if not os.path.exists(limit_vhigh):
		print "**ERR: file not found", limit_vhigh
		sys.exit(-1)

	# Find the antecedent rainfall boolean 95th percentile accumulation file for the area
	ant_rainfall_bool 	= os.path.join(config.data_dir,"ant_r", dx, ymd, "ant_r_%s_bool.tif" % (ymd))
	if force or not os.path.exists(ant_rainfall_bool):
		cmd = "python antecedent_rainfall.py --region "+dx+ " --date "+date
		if verbose:
			cmd += " -v"
		if force:
			cmd += " -f"
		execute(cmd)
	
	# Find the daily rainfall accumulation file for the area from yesterday
	daily_rainfall 	= os.path.join(config.data_dir,"trmm", dx, yymd, "trmm_24_%s_%s_1km.tif" % (dx,yymd))
	if not os.path.exists(daily_rainfall):
		print "**ERR: file not found", daily_rainfall
		sys.exit(-1)
		
	# Find susceptibility map
	susmap 	= os.path.join(config.data_dir, "susmap.2", "susmap_%s_bool.tif" %(dx))
	if not os.path.exists(susmap):
		print "**ERR: file not found", susmap
		sys.exit(-1)

	forecast_landslide_bin 				= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast.%s.tif" %(ymd))
	forecast_landslide_bin_rgb 			= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast.%s_rgb.tif" %(ymd))

	forecast_landslide_100m_bin 		= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast.%s_100m.tif" %(ymd))
	forecast_landslide_100m_bin_rgb 	= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd, "landslide_nowcast.%s_100m_rgb.tif" %(ymd))	
	
	color_file							= "./cluts/landslide_colors.txt"
	
	shp_file 							= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast.%s.shp" % (ymd))
	geojson_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast.%s.geojson" % (ymd))
	
	topojson_file						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast.%s.topojson" % (ymd))
	topojson_gz_file					= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast.%s.topojson.gz" % (ymd))
	thumbnail_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, ymd, "landslide_nowcast.%s.thn.png" % (ymd))
	static_file 						= os.path.join(config.data_dir,"landslide_nowcast", dx, "%s_static.tiff" % (dx))

	if force or not os.path.exists(forecast_landslide_bin):
		if verbose:
			"Processing forecast landslide model for %s..." % date
			
		if verbose:
			print "Loading ", susmap

		# STEP 1 Susceptibility Map as Boolean
		smap_ds			= gdal.Open( susmap )
		smap_ncols 		= smap_ds.RasterXSize
		smap_nrows 		= smap_ds.RasterYSize
		smap_band 		= smap_ds.GetRasterBand(1)
		smap_data 		= smap_band.ReadAsArray(0, 0, smap_ncols, smap_nrows )
		smap_nodata		= smap_band.GetNoDataValue()
		projection   	= smap_ds.GetProjection()
		geotransform 	= smap_ds.GetGeoTransform()

		xorg			= geotransform[0]
		yorg  			= geotransform[3]
		pres			= geotransform[1]
		xmax			= xorg + geotransform[1]* smap_ds.RasterXSize
		ymax			= yorg - geotransform[1]* smap_ds.RasterYSize
			
		if verbose:
			print "Loaded", susmap, smap_ncols, smap_nrows, smap_nodata
			
		if verbose:
			print "Loading ", daily_rainfall

		rainfall_ds		= gdal.Open( daily_rainfall )
		rainfall_ncols 	= rainfall_ds.RasterXSize
		rainfall_nrows 	= rainfall_ds.RasterYSize
		rainfall_band 	= rainfall_ds.GetRasterBand(1)
		rainfall_data 	= rainfall_band.ReadAsArray(0, 0, rainfall_ncols, rainfall_nrows )
		if verbose:
			print "Loaded", daily_rainfall, rainfall_ncols, rainfall_nrows
	
		assert( smap_ncols == rainfall_ncols)
		assert( smap_nrows == rainfall_nrows)

		if verbose:
			print "Loading ", ant_rainfall_bool

		ant_rainfall_ds			= gdal.Open( ant_rainfall_bool )
		ant_rainfall_ncols 		= ant_rainfall_ds.RasterXSize
		ant_rainfall_nrows 		= ant_rainfall_ds.RasterYSize
		ant_rainfall_band 		= ant_rainfall_ds.GetRasterBand(1)
		ant_rainfall_data_bool 	= ant_rainfall_band.ReadAsArray(0, 0, ant_rainfall_ncols, ant_rainfall_nrows )

		assert( smap_ncols == ant_rainfall_ncols)
		assert( smap_nrows == ant_rainfall_nrows)
	
		if verbose:
			print "cols %d rows %d" %(ant_rainfall_ncols, ant_rainfall_nrows)

		if verbose:
			print "Loading ", limit_low
			
		limit_low_ds		= gdal.Open( limit_low )
		limit_low_ncols 	= limit_low_ds.RasterXSize
		limit_low_nrows 	= limit_low_ds.RasterYSize
		limit_low_band 		= limit_low_ds.GetRasterBand(1)
		limit_low_data 		= limit_low_band.ReadAsArray(0, 0, limit_low_ncols, limit_low_nrows )

		assert( smap_ncols == limit_low_ncols)
		assert( smap_nrows == limit_low_nrows)
		
		if verbose:
			print "Loading ", limit_high
			
		limit_high_ds		= gdal.Open( limit_high )
		limit_high_ncols 	= limit_high_ds.RasterXSize
		limit_high_nrows 	= limit_high_ds.RasterYSize
		limit_high_band 	= limit_high_ds.GetRasterBand(1)
		limit_high_data 	= limit_high_band.ReadAsArray(0, 0, limit_high_ncols, limit_high_nrows )

		assert( smap_ncols == limit_high_ncols)
		assert( smap_nrows == limit_high_nrows)

		limit_vhigh_ds		= gdal.Open( limit_vhigh )
		limit_vhigh_ncols 	= limit_vhigh_ds.RasterXSize
		limit_vhigh_nrows 	= limit_vhigh_ds.RasterYSize
		limit_vhigh_band 	= limit_vhigh_ds.GetRasterBand(1)
		limit_vhigh_data 	= limit_vhigh_band.ReadAsArray(0, 0, limit_vhigh_ncols, limit_vhigh_nrows )

		assert( smap_ncols == limit_vhigh_ncols)
		assert( smap_nrows == limit_vhigh_nrows)

		# Step 2
		# low percentile current rainfall raster
		rr_low = numpy.zeros(shape=(rainfall_nrows,rainfall_ncols))
		rr_low[rainfall_data > limit_low_data] = 1
		
		if verbose:
			save_tiff(dx, rr_low,"rr_low", smap_ds)
			
		# Step 3
		# high percentile current rainfall raster
		rr_high = numpy.zeros(shape=(rainfall_nrows,rainfall_ncols))
		rr_high[rainfall_data > limit_high_data] = 1

		rr_high[rainfall_data > limit_vhigh_data] = 2

		if verbose:
			save_tiff(dx, rr_high, "rr_high", smap_ds)
			
		# inverted antecedent boolean raster
		iabr = numpy.zeros(shape=(ant_rainfall_nrows,ant_rainfall_ncols))
		iabr[ant_rainfall_data_bool == 0] = 1
		if verbose:
			save_tiff(dx, iabr, "iabr", smap_ds)
			
		# Step 4
		# antecedent boolean raster is ant_rainfall_data
		step_8_1 = numpy.logical_and(ant_rainfall_data_bool, rr_low)
		if verbose:
			save_tiff(dx, step_8_1, "step_8_1", smap_ds)
		
		step_8_2 = numpy.logical_and(iabr, rr_high)
		if verbose:
			save_tiff(dx, step_8_2, "step_8_2", smap_ds)
		
		step_8_3 = numpy.logical_or(step_8_1, step_8_2)
		if verbose:
			save_tiff(dx, step_8_3, "step_8_3", smap_ds)
		
		# Clear no data
		smap_data[ smap_data == smap_nodata ] = 0

		step_8_4 = numpy.logical_and(smap_data, step_8_3)
		if verbose:
			save_tiff(dx, step_8_4, "step_8_4", smap_ds)
			
		# Write the file
		driver 			= gdal.GetDriverByName("GTiff")
		cur_ds 			= driver.Create(forecast_landslide_bin, smap_ncols, smap_nrows, 1, gdal.GDT_Byte)
		outband 		= cur_ds.GetRasterBand(1)
		
		outband.WriteArray(step_8_4, 0, 0)
		outband.SetNoDataValue(smap_nodata)
		
		cur_ds.SetGeoTransform( geotransform )
		cur_ds.SetGeoTransform( geotransform )

		smap_ds 		= None
		rainfall_ds 	= None
		ant_rainfall_ds = None
		cur_ds			= None
		limit_low_ds	= None
		limit_high_ds	= None

	if 0:
		# Now let's colorize it
		if 1: #force or not os.path.exists(forecast_landslide_bin_rgb):
			cmd = "gdaldem color-relief -alpha " +  forecast_landslide_bin + " " + color_file + " " + forecast_landslide_bin_rgb
			if verbose:
				print cmd
			err = os.system(cmd)
			if err != 0:
				print('ERROR: slope file could not be generated:', err)
				sys.exit(-1)
	
	if 0:

		infile 	= forecast_landslide_bin_rgb
		file 	= forecast_landslide_bin_rgb + ".pgm"

		if force or not os.path.exists(file):
			# subset it, convert red band (band 1) and output to .pgm using PNM driver
			cmd = "gdal_translate  -q -scale 0 1 0 65535 " + infile + " -b 1 -of PNM -ot Byte "+file
			execute( cmd )
			execute("rm -f "+file+".aux.xml")

		# -i  		invert before processing
		# -t 2  	suppress speckles of up to this many pixels. 
		# -a 1.5  	set the corner threshold parameter
		# -z black  specify how to resolve ambiguities in path decomposition. Must be one of black, white, right, left, minority, majority, or random. Default is minority
		# -x 		scaling factor
		# -L		left margin
		# -B		bottom margin

		if force or not os.path.exists(file+".geojson"):
			cmd = str.format("potrace -z black -a 1.5 -t 2 -i -b geojson -o {0} {1} -x {2} -L {3} -B {4} ", file+".geojson", file, pres, xorg, ymax ); 
			execute(cmd)

		if force or not os.path.exists(file+".topojson.gz"):
			cmd = str.format("topojson -o {0} --simplify-proportion 0.5 -p nowcast=1 -- landslide_nowcast={1}", file+".topojson", file+".geojson"); 
			execute(cmd)
	
			cmd = "gzip -f %s" % (file+".topojson")
			execute(cmd)

			cmd = "mv " + file+".topojson.gz" + " " + topojson_gz_file
			execute(cmd)
		
		#create the thumbnail
		tmp_file = thumbnail_file + ".tmp.tif"
		if force or not os.path.exists(thumbnail_file):
			cmd="gdalwarp -overwrite -q -multi -ts %d %d -r cubicspline -co COMPRESS=LZW %s %s" % (thn_width, thn_height, forecast_landslide_bin_rgb, tmp_file )
			execute(cmd)
			cmd = "composite %s %s %s" % ( tmp_file, static_file, thumbnail_file)
			execute(cmd)
			execute("rm -f "+tmp_file)
			
		cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + topojson_gz_file
		if verbose:
			cmd += " --verbose"
		if force:
			cmd += " --force"
		execute(cmd)

		cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + thumbnail_file
		if verbose:
			cmd += " --verbose"
		if force:
			cmd += " --force"	
		execute(cmd)

		cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + forecast_landslide_bin
		if verbose:
			cmd += " --verbose"
		if force:
			cmd += " --force"	
		execute(cmd)
	
		if not verbose:
			files = [	forecast_landslide_bin_rgb,
						forecast_landslide_100m_bin,
						forecast_landslide_100m_bin_rgb, 
						file,file+".geojson", 
						file+".geojson",
						forecast_landslide_bin, 
						forecast_landslide_bin_rgb   ]
			execute("rm -f "+" ".join(files))
	
	
def process(mydir, scene, s3_bucket, s3_folder, zoom):
	global verbose, force
	
	fullName = os.path.join(mydir, scene+".tif")
	if not os.path.exists(fullName):
		print "File does not exist", fullName
		sys.exit(-1)
	
	if verbose:
		print "Processing", fullName
		
	geojsonDir	= os.path.join(mydir,"geojson")
	if not os.path.exists(geojsonDir):            
		os.makedirs(geojsonDir)

	levelsDir	= os.path.join(mydir,"levels")
	if not os.path.exists(levelsDir):            
		os.makedirs(levelsDir)

	shpDir	= os.path.join(mydir,"shp")
	cmd = "rm -rf " + shpDir
	execute(cmd)
	os.makedirs(shpDir)

	merge_filename 		= os.path.join(geojsonDir, "%s.geojson" % scene)
	topojson_filename 	= os.path.join(mydir, "%s.topojson" % scene)
	browse_filename 	= os.path.join(mydir, "%s_browse.tif" % scene)
	subset_filename 	= os.path.join(mydir, "%s_small_browse.tif" % scene)
	osm_bg_image		= os.path.join(mydir, "osm_bg.png")
	sw_osm_image		= os.path.join(mydir, "%s_thn.jpg" % scene)
	shapefile_gz		= os.path.join(mydir, "%s.shp.gz" % scene)

	levels 				= [2,1]
	
	# From http://colorbrewer2.org/
	#hexColors 			= ["#ffffe5", "#feb24c","#f03b20"]
	hexColors 			= ["#feb24c","#f03b20"]
	
	ds 					= gdal.Open( fullName )
	band				= ds.GetRasterBand(1)
	data				= band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize )
	
	if force or not os.path.exists(topojson_filename+".gz"):
		for l in levels:
			fileName 		= os.path.join(levelsDir, scene+"_level_%d.tif"%l)
			CreateLevel(l, geojsonDir, fileName, ds, data, "landslide_nowcast", force,verbose)
	
		jsonDict = dict(type='FeatureCollection', features=[])
	
		for l in reversed(levels):
			fileName 		= os.path.join(geojsonDir, "landslide_nowcast_level_%d.geojson"%l)
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

		if verbose:
			cmd 	= "gzip -f --keep "+ topojson_filename
		else:
			cmd 	= "gzip -f "+ topojson_filename
				
		execute(cmd)

	# Convert to shapefile		
	#if force or not os.path.exists(shpDir) and os.path.exists(merge_filename):
	#	cmd= "ogr2ogr -f 'ESRI Shapefile' %s %s" % ( shpDir, merge_filename)
	#	execute(cmd)
	
	#if force or not os.path.exists(shapefile_gz):
	#	cmd 	= "cd %s; tar -cvzf %s shp" %(mydir, shapefile_gz)
	#	execute(cmd)
	
	if force or not os.path.exists(sw_osm_image):
		MakeBrowseImage(ds, browse_filename, subset_filename, osm_bg_image, sw_osm_image,levels, hexColors, force, verbose, zoom)
		
	ds = None
	
	file_list = [ sw_osm_image, topojson_filename+".gz", fullName ]
	
	CopyToS3( s3_bucket, s3_folder, file_list, force, verbose )
		
	if not verbose:
		verbose = 1

		cmd = "rm -f %s %s %s %s" %(osm_bg_image, subset_filename, subset_filename+".aux.xml", browse_filename )
		execute(cmd)

		cmd = "rm -rf "+shpDir
		execute(cmd)
		cmd = "rm -rf "+levelsDir
		execute(cmd)
		cmd = "rm -rf "+geojsonDir
		execute(cmd)
		
		fpath 	= os.path.join(config.data_dir,"landslide_nowcast", region, ymd)
		cmd	= "rm -rf " + os.path.join(fpath,"iabr*")
		execute(cmd)
		cmd	= "rm -rf " + os.path.join(fpath,"rr_*")
		execute(cmd)
		cmd	= "rm -rf " + os.path.join(fpath,"step_*")
		execute(cmd)

		
		
		
def generate_map( dx, date, year, doy ):
	# make sure it exists
	region		= config.regions[dx]
	
	if verbose:
		print "Processing Forecast Landslide Map for Region:", dx, region['name']	
	
	# Destination Directory
	mydir			= os.path.join(config.data_dir, "landslide_nowcast", dx, ymd)
	if not os.path.exists(mydir):
		os.makedirs(mydir)

	build_tif(dx, region, mydir, date )
	
	s3_folder	= os.path.join("landslide_nowcast", str(year), doy)
	s3_bucket	= region['bucket']
	
	scene 				=  "landslide_nowcast.%s" %(ymd)
	process(mydir, scene, s3_bucket, s3_folder, region['thn_zoom'])
	
	
# =======================================================================
# Main
# python landslide_nowcast.py --region d03 --date 2015-04-07 -v
if __name__ == '__main__':
	
	parser 		= argparse.ArgumentParser(description='Generate Forecast Landslide Estimates')
	apg_input 	= parser.add_argument_group('Input')
		
	apg_input.add_argument("-f", "--force", 	action='store_true', help="Forces new products to be generated")
	apg_input.add_argument("-v", "--verbose", 	action='store_true', help="Verbose Flag")
	apg_input.add_argument("-r", "--region", 	required=True, help="Region: d02|d03")
	apg_input.add_argument("-d", "--date", 		help="date: 2014-11-20 or today if not defined")
	
	todaystr	= date.today().strftime("%Y-%m-%d")
	
	options 	= parser.parse_args()
	force		= options.force
	verbose		= options.verbose
	region		= options.region
	dt			= options.date or todaystr
	
	assert(config.regions[region])
	
	today		= parse(dt)
	year		= today.year
	month		= today.month
	day			= today.day
	ymd			= "%d%02d%02d" % (year, month, day)
	doy			= today.strftime('%j')

	yesterday	= today - timedelta(days=1)
	yyear		= yesterday.year
	ymonth		= yesterday.month
	yday		= yesterday.day
	yymd		= "%d%02d%02d" % (yyear, ymonth, yday)
	
	if verbose:
		print "generating forecast for", today.strftime("%Y-%m-%d")
		
	generate_map(region, dt, year, doy)
	
	print "Done."
