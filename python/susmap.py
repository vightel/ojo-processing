#!/usr/bin/env python
#
# Created on 9/27/2012 Pat Cappelaere - Vightel Corporation
#
#
# Processes the susceptibility map from Thomas Stanley
# It generates the RGB map and bool map
#

import sys, os, inspect
import argparse
from osgeo import osr, gdal

# Site configuration
import config

verbose = 0
force 	= 0

def execute( cmd ):
	if verbose:
		print cmd
	os.system(cmd)
	
def generate_map( dx ):
	# make sure it exists
	region		= config.regions[dx]
	
	if verbose:
		print "Processing Susceptibility Map for Region:", dx, region['name']	
	
	color_file				= os.path.join("./cluts", 	"susmap_colors2.txt")
	basedir					= "susmap.2"
	
	input_file				= os.path.join(config.data_dir, basedir, "susmap_"+ dx + ".tif")
	input_file_bool			= os.path.join(config.data_dir, basedir, "susmap_"+ dx + "_bool.tif")
	input_file_warped		= os.path.join(config.data_dir, basedir, "susmap_"+ dx + "_warped.tif")
	rgb_warped_file			= os.path.join(config.data_dir, basedir, "susmap_"+ dx + "_warped_rgb.tif")
	rgb_output_file			= os.path.join(config.data_dir, basedir, "susmap_"+ dx + "_rgb.tif")
	output_file_shp			= os.path.join(config.data_dir, basedir, "susmap_"+ dx + ".shp")
	output_file_geojson		= os.path.join(config.data_dir, basedir, "susmap_"+ dx + ".geojson")
	output_file_topojson	= os.path.join(config.data_dir, basedir, "susmap_"+ dx + ".topojson")
	mbtiles_dir				= os.path.join(config.data_dir, basedir, "mbtiles_"+ dx)
	mbtiles_fname 			= os.path.join(config.data_dir, basedir, "susmap_"+ dx + ".mbtiles")
	
	# get raster size
	src_ds 			= gdal.Open( input_file )
	ncols 			= src_ds.RasterXSize
	nrows 			= src_ds.RasterYSize
	
	xres	 		= ncols * 10
	
	region			= config.regions[dx]
	tzoom			= region['tiles-zoom']

	# Modified to accomodate issues with ojo-tiler -> Mapbox
	
	# increase resolution by 100 and do cubic spline interpolation to smooth the rater
	#if force or not os.path.exists(input_file_warped):		
	#	cmd = "gdalwarp -ts "+ str(xres) + " 0 -r cubicspline -multi -co 'TFW=YES' " + input_file + " " + input_file_warped
	#	execute(cmd)
	
	# colorize interpolated raster
	#if force or not os.path.exists(rgb_warped_file):		
	#	cmd = "gdaldem color-relief -alpha -of GTiff "+input_file_warped+" " + color_file + " " + rgb_warped_file
	#	execute(cmd)

	# generate mbtiles
	#if force or not os.path.exists(mbtiles_fname):		
	#	cmd = "./gdal2tiles.py -z "+ tzoom + " " + rgb_output_file  + " " + mbtiles_dir
	#	execute(cmd)

	#	cmd = "./mb-util " + mbtiles_dir  + " " + mbtiles_fname
	#	execute(cmd)

	# copy mbtiles to S3
	#if force or not os.path.exists(mbtiles_fname):
	#	bucketName = region['bucket']
	#	cmd = "aws-copy.py --bucket "+bucketName+ " --file " + mbtiles_fname
	#	if verbose:
	#		cmd += " --verbose "
	#	execute(cmd)

	#	cmd = "rm -rf "+ mbtiles_dir
	#	execute(cmd)
		
	# Modification: Just recolor initial raster at 1km
	# colorize interpolated raster
	if force or not os.path.exists(rgb_output_file):		
		cmd = "gdaldem color-relief -alpha -of GTiff "+input_file+" " + color_file + " " + rgb_output_file
		execute(cmd)
	
	# generate boolean map from original image
	if force or not os.path.exists(input_file_bool):
		if verbose:
			print "generate bool susceptibility map", input_file_bool
		drv 	= gdal.GetDriverByName('GTiff')
		src_ds 	= gdal.Open( input_file )
	
		out_ds 	= drv.CreateCopy(input_file_bool, src_ds, 0, [ 'COMPRESS=DEFLATE' ] )
		band 	= out_ds.GetRasterBand(1)
		data 	= band.ReadAsArray(0, 0, out_ds.RasterXSize, out_ds.RasterYSize )
		nodata	= band.GetNoDataValue()
		
		# 1-5, 15 is water/no_data
		
		data[data==nodata]  = 0
		data[data==15]  	= 0
		data[data==1]  		= 0
		data[data>1] 		= 1
		
		ct = gdal.ColorTable()

		ct.SetColorEntry( 0, (0, 0, 0, 255))
		ct.SetColorEntry( 1, (255,	255, 255, 255))
		
		band.SetRasterColorTable(ct)
		band.WriteArray(data, 0, 0)
		
		out_ds	= None
		src_ds	= None
		
	if 0:
		cmd = "gdal_contour -a risk " + rgb_output_file+ " "+ output_file_shp + " -i 1"
		if verbose:
			print cmd
		os.system(cmd)

		cmd = "ogr2ogr -f GeoJSON "+ output_file_geojson + " " + output_file_shp
		if verbose:
			print cmd
		os.system(cmd)
	
		cmd = "topojson -o "+ output_file_topojson + " " + output_file_geojson
		if verbose:
			print cmd
		os.system(cmd)
	
	
# =======================================================================
# Main
#
if __name__ == '__main__':
	
	parser = argparse.ArgumentParser(description='Process susceptibility maps')
	apg_input = parser.add_argument_group('Input')
	apg_input.add_argument("-f", "--force", 	action='store_true', help="Forces new product to be generated")
	apg_input.add_argument("-v", "--verbose", 	action='store_true', help="Verbose on/off")
	apg_input.add_argument("-r", "--region", 	required=True, help="Region d02|d03")
	options 	= parser.parse_args()
	force		= options.force
	verbose		= options.verbose
	region		= options.region

	generate_map(region)
	print "Done."
