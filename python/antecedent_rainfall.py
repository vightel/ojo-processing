#!/usr/bin/env python
#
# Created on 9/27/2012 Pat Cappelaere - Vightel Corporation
#
# Computes Antecedent Rainfall over the last 60 days
#
# Requirements:
#	gdal, numpy pytrmm...
#
#

import numpy, os, sys, inspect, math
from osgeo import osr, gdal
from ftplib import FTP
import datetime
from datetime import date
import warnings
from gzip import GzipFile
import pygrib
import pyproj
import argparse
from dateutil.parser import parse

from osgeo import gdal

# Site configuration
import config

force 				= 0
verbose				= 0
antecedent_data		= None
smos_dir			= None
smos_regional_dir	= None
smos_reg_daily_dir	= None

def checkdirs(dx, ymd):
	global smos_dir, smos_regional_dir, smos_reg_daily_dir
	
	# required directories
	smos_dir			=  os.path.join(config.data_dir,"ant_r")
	smos_regional_dir	=  os.path.join(smos_dir, dx)
	smos_reg_daily_dir	=  os.path.join(smos_regional_dir, ymd)

	if not os.path.exists(smos_dir):
	    os.makedirs(smos_dir)

	if not os.path.exists(smos_regional_dir):
	    os.makedirs(smos_regional_dir)

	if not os.path.exists(smos_reg_daily_dir):
	    os.makedirs(smos_reg_daily_dir)

def get_trmm_data(dt, region):
	cmd = "python trmm_process.py "
	if verbose:
		cmd += " -v "
	if force:
		cmd += " -f "
	
	cmd += " --date " + dt
	cmd += " --region " + region
	
	if verbose:
		print cmd
	os.system(cmd)
	
def process_region(dx, idx, weight, ymd):
	global antecedent_data
	
	trmm_dir 	=  os.path.join(config.data_dir,"trmm", dx, ymd)
	trmm_file 	=  os.path.join(trmm_dir, "trmm_24_"+dx+"_"+ymd+"_1km.tif")
	
	if not os.path.exists(trmm_file):
		print "file does not exist", trmm_file
		sys.exit(-1)
	
	if verbose:
		print "Processing", trmm_file, idx, weight
	
	src_ds 			= gdal.Open( trmm_file)
	band 			= src_ds.GetRasterBand(1)
	rasterXSize 	= src_ds.RasterXSize
	rasterYSize 	= src_ds.RasterYSize
	data 			= band.ReadAsArray(0, 0, rasterXSize, rasterYSize ).astype(float)
	
	data 			*= weight
	
	if idx == 1:
		antecedent_data = data
	else:
		antecedent_data += data
		
	band	= None
	src_ds 	= None


def save_tif(fname, data, ds, type, ct):
	if verbose:
		print "saving", fname
		
	format 		= "GTiff"
	driver 		= gdal.GetDriverByName( format )
	dst_ds	 	= driver.Create( fname, ds.RasterXSize, ds.RasterYSize, 1, type, [ 'COMPRESS=DEFLATE' ] )
	band 		= dst_ds.GetRasterBand(1)
	
	band.WriteArray( data )
	
	dst_ds.SetGeoTransform( ds.GetGeoTransform() )
	dst_ds.SetProjection( ds.GetProjection() )
	
	if ct:
		ct = gdal.ColorTable()
		ct.SetColorEntry( 0, (0, 0, 0, 0) )
		ct.SetColorEntry( 1, (255, 0, 0, 255) )
		band.SetRasterColorTable(ct)
	
	dst_ds = None
#
# ======================================================================
#
if __name__ == '__main__':
	#global antecedent_data
	
	parser 		= argparse.ArgumentParser(description='Antecedent Rainfall Processing')
	apg_input 	= parser.add_argument_group('Input')

	apg_input.add_argument("-f", "--force", 	action='store_true', help="forces new product to be generated")
	apg_input.add_argument("-v", "--verbose", 	action='store_true', help="Verbose Flag")
	apg_input.add_argument("-r", "--region", 	required=True, 		 help="Region: d02|d03")
	apg_input.add_argument("-d", "--date", 		required=True, 		 help="Date: 2014-11-20")
	
	options = parser.parse_args()

	force			= options.force
	verbose			= options.verbose
	region			= options.region
	tdate			= options.date
	
	today			= parse(tdate)
	year			= today.year
	month			= today.month
	day				= today.day
	
	starting_ymd	= "%d%02d%02d" % (year, month, day)

	checkdirs(region, starting_ymd)

	# Test for one day
	# d = today + datetime.timedelta(days= -1)

	sum_weights		= 0.0
	
	for i in range(1,61):	# days 1...60
		d 			= today + datetime.timedelta(days= -i)
		dt			= d.strftime('%Y-%m-%d')
		f			= float(i)
		weight		= 1.0/math.pow(f,0.5)
		sum_weights	+= weight
					
		year		= d.year
		month		= d.month
		day			= d.day
		ymd 		= "%d%02d%02d" % (year, month, day)

		trmm_dir 	= os.path.join(config.data_dir,"trmm", region, ymd)
		trmm_file 	= os.path.join(trmm_dir, "trmm_24_"+region+"_"+ymd+"_1km.tif")
	
		if not os.path.exists(trmm_file):
			get_trmm_data(dt, region)

		process_region(region, i, weight, ymd )

	if verbose:
		print "Normalized by", sum_weights
	
	# we are in 10th of mm -> convert back to mm
	sum_weights 			*= 10.0
	
	antecedent_data 		/= sum_weights
	
	output_fileName			=  os.path.join(smos_reg_daily_dir, "ant_r_" + starting_ymd + ".tif")
	output_bool_fileName	=  os.path.join(smos_reg_daily_dir, "ant_r_" + starting_ymd + "_bool.tif")
	thresholds_fileName		=  os.path.join(smos_dir, "%s_50ar.tif" % region)
	
	t_ds 					= gdal.Open( thresholds_fileName)
	band 					= t_ds.GetRasterBand(1)
	rasterXSize 			= t_ds.RasterXSize
	rasterYSize 			= t_ds.RasterYSize
	tdata 					= band.ReadAsArray(0, 0, rasterXSize, rasterYSize )

	#save_tif(output_fileName, antecedent_data, t_ds, gdal.GDT_UInt16, 0)
	save_tif(output_fileName, antecedent_data, t_ds, gdal.GDT_Float32, 0)
	
	if verbose:
		print "Loaded Rainfall Thresholds:", thresholds_fileName, numpy.min(tdata), numpy.mean(tdata), numpy.max(tdata)
		print "Antecedent Rainfall Data:", numpy.min(antecedent_data), numpy.mean(antecedent_data), numpy.max(antecedent_data)
	
	data_result				= (antecedent_data>tdata)
	
	save_tif(output_bool_fileName, data_result, t_ds, gdal.GDT_Byte, 1)
		
	# Once we're done, close properly the dataset
	t_ds		= None

	if verbose:
		print "Done."
