#!/usr/bin/env python
#
# Created on 9/27/2012 Pat Cappelaere - Vightel Corporation
# Updated on 07/17/2015 Pat Cappelaere - Vightel Corporation
#  Global Processing
#
# Requirements:
#	gdal, numpy pytrmm...
#
import numpy, sys, os, inspect, urllib
import argparse
import numpy
import json

from datetime import date
from dateutil.parser import parse

from osgeo import osr, gdal
from ftplib import FTP
from datetime import date, timedelta
from s3 import CopyToS3

from browseimage import MakeBrowseImage 
from level import CreateLevel

# Site configuration
import config

url		= "http://eagle1.umd.edu"

class GFMS:
	def __init__( self, inpath, force, verbose ):
		self.inpath 	= inpath
		self.force		= force
		self.verbose	= verbose

	def execute(self, cmd):
		if(self.verbose):
			print cmd
		os.system(cmd)
		
	def get_latest_file(self):
		path 			= "%s/flood/download/%s/%s/Flood_byStor_%s%02d00.bin" % (url, year, ym, ym, day)
		fname 			= "Flood_byStor_%s%02d00.bin" % (ym, day)
		fullname		= os.path.join(self.inpath, "gfms", ymd, fname)
		
		if not os.path.exists(fullname):
			if self.verbose:
				print "retrieving ", path, " -> ", fullname
			urllib.urlretrieve(path, fullname)
				
		
	def get_latest_highres_file(self):
		path 			= "%s/flood/download1km/%s/%s/Routed_%s%02d00.bin" % (url, year, ym, ym, day)
		fname 			= "Routed_%s%02d00.bin" % (ym, day)
		fullname		= os.path.join(self.inpath, "gfms", ymd, fname)
		
		def reporthook(blocks_read, block_size, total_size):
			if not blocks_read:
				print 'Connection opened'
				return
			if total_size < 0:
				# Unknown size
				print 'Read %d blocks' % blocks_read
			else:
				amount_read = blocks_read * block_size
				#print 'Read %d blocks, or %d/%d' % (blocks_read, amount_read, total_size)
			return
					
		if not os.path.exists(fullname):
			if self.verbose:
				print "retrieving ", path, " -> ", fullname
				urllib.urlretrieve(path, fullname, reporthook)
			else:
				urllib.urlretrieve(path, fullname)
				
		else:
			print "highres exists:", fullname

	def process_highres_region(self, dx, dt):
		region 		= config.regions[dx]
		bbox		= region['bbox']
		tzoom		= region['tiles-zoom']
		pxsize		= region['pixelsize']
		thn_width   = region['thn_width']
		thn_height  = region['thn_height']
		bucketName 	= region['bucket']
		
		if self.verbose:
			print "gfms highres processing region:", dx, dt
			
		output_file			= os.path.join(self.inpath, "gfms", ymd, "Routed_%s%02d00.tif" % (ym, day))
		subset_file			= os.path.join(self.inpath, "gfms", dx, ymd, "Routed_%s_subset_%s.tif" % (dt, dx))
		subset_rgb_file		= os.path.join(self.inpath, "gfms", dx, ymd, "Routed_%s_subset_%s_rgb.tif" % (dt, dx))
		
		supersampled_file		= os.path.join(self.inpath, "gfms", dx, ymd, "Routed_%s_hr_subset_%s.tif" % (dt, dx))
		supersampled_file_rgb	= os.path.join(self.inpath, "gfms", dx, ymd, "Routed_%s_hr_subset_%s_rgb.tif" % (dt, dx))
		
		color_file 			= os.path.join("cluts", "gfms_colors.txt")
		
		shp_file 			= os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_"+dx+"_"+ymd+".shp")
		geojson_file 		= os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_"+dx+"_"+ymd+".geojson")
		topojson_file		= os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_"+dx+"_"+ymd+".topojson")
		topojson_gz_file	= os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_"+dx+"_"+ymd+".topojson.gz")
		thumbnail_file 		= os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.thn.png" % (dx,ymd))
		
		static_file 		= os.path.join(config.data_dir,"gfms", dx, "%s_static.tiff" % (dx))
		
		#mbtiles_dir 		= os.path.join(config.data_dir,"mbtiles", "gfms_highres_%s_%s" % (dt, dx))
		#mbtiles_fname 		= mbtiles_dir+".mbtiles"
		
		# subset it to our BBOX
		# use ullr
		if self.force or not os.path.exists(subset_file):
			lonlats	= "" + str(bbox[0]) + " " + str(bbox[3]) + " " + str(bbox[2]) + " " + str(bbox[1])	
			cmd 	= "gdal_translate -q -projwin " + lonlats +" "+ output_file+ " " + subset_file
			self.execute(cmd)
			
		if self.force or not os.path.exists(subset_rgb_file):		
			cmd = "gdaldem color-relief -q -alpha "+ subset_file + " " + color_file + " " + subset_rgb_file
			self.execute(cmd)

		# resample it at 100m
		if force or not os.path.exists(supersampled_file):			
			cmd = "gdalwarp -q -tr %f %f -r cubicspline %s %s" % (pxsize/10,pxsize/10,subset_file,supersampled_file)
			self.execute(cmd)

		# color it for debugging
		if force or not os.path.exists(supersampled_file_rgb):			
			cmd = "gdaldem color-relief -q -alpha " + supersampled_file + " " + color_file + " " + supersampled_file_rgb
			self.execute(cmd)
		
		if self.force or not os.path.exists(shp_file):
			cmd = "gdal_contour -q -a risk -fl 100 -fl 200 %s %s" % ( supersampled_file, shp_file )
			self.execute(cmd)
	
		if self.force or not os.path.exists(geojson_file):
			cmd = "ogr2ogr -f geoJSON %s %s" %( geojson_file, shp_file) 
			self.execute(cmd)
	
		if self.force or not os.path.exists(topojson_file):
			cmd = "topojson --simplify-proportion 0.75  --bbox -p risk -o %s -- flood_24hr_forecast=%s" % (topojson_file, geojson_file ) 
			self.execute(cmd)
	
		if self.force or not os.path.exists(topojson_gz_file):
			cmd = "gzip %s" % (topojson_file)
			self.execute(cmd)
		
		tmp_file = thumbnail_file + ".tmp.tif"
		if force or not os.path.exists(thumbnail_file):
			cmd="gdalwarp -overwrite -q -multi -ts %d %d -r cubicspline -co COMPRESS=LZW %s %s" % (thn_width, thn_height, supersampled_file_rgb, tmp_file )
			self.execute(cmd)
			cmd = "composite -blend 60 %s %s %s" % ( tmp_file, static_file, thumbnail_file)
			self.execute(cmd)
			self.execute("rm "+tmp_file)
		
		cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + topojson_gz_file
		if verbose:
			cmd += " --verbose"
		self.execute(cmd)

		cmd = "./aws-copy.py --bucket " + bucketName + " --folder " + ymd + " --file " + thumbnail_file
		if verbose:
			cmd += " --verbose"
		self.execute(cmd)
	
		delete_files = [
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s_4326.tif" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.dbf" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.prj" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.shp" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.shx" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "gfms_24_%s_%s.geojson" % (dx,ymd)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "Routed_%s_hr_subset_%s.tif" % (ymd, dx)),
			os.path.join(config.data_dir,"gfms", dx, ymd, "Routed_%s_subset_*" % (ymd)),
		]
	
		if not verbose:		# probably debugging, so do not dispose of artifacts
			cmd = "rm -f "+ " ".join(delete_files)
			self.execute(cmd)
			
	def process_highres_d02(self, dt):
		self.process_highres_region("d02", dt)

	def process_highres_d03(self, dt):
		self.process_highres_region("d03", dt)
				
	def process_highres(self):
		input_fname 			= "Routed_%s%02d00.bin" % (ym, day)
		input_fullname			= os.path.join(self.inpath, "gfms", ymd, input_fname)
		output_fname 			= "Routed_%s%02d00.tif" % (ym, day)
		output_fullname			= os.path.join(self.inpath, "gfms", ymd, output_fname)
		output_rgb_fname		= "Routed_%s%02d00_rgb.tif" % (ym, day)
		
		output_rgb_fullname		= os.path.join(self.inpath, "gfms", ymd, output_rgb_fname)
		color_file 				= os.path.join("cluts", "gfms_colors.txt")
		
		#mbtiles_dir 			= os.path.join(config.data_dir,"mbtiles", "gfms_highres_%s%02d00" % (ym, day))
		#mbtiles_fname 			= mbtiles_dir+".mbtiles"

		if self.force or not os.path.exists(output_fullname):		
			rows 	= 12001
			cols	= 36870
			size	= rows*cols
		
			fd		= open(input_fullname, 'rb')
			shape	= (rows, cols)
			data 	= numpy.fromfile(file=fd,dtype=numpy.float32, count=size).reshape(shape)

			print "stats:", data.size, data.min(), data.mean(), data.max(), data.std()

			x		= -127.2458335
			y		= 50.0001665
			res		= 0.00833
			nodata	= -9999
			
			# Create gtif
			driver = gdal.GetDriverByName("GTiff")
			dst_ds = driver.Create(output_fullname, cols, rows, 1, gdal.GDT_Float32)
			# top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution
			dst_ds.SetGeoTransform( [ x, res, 0, y, 0, -res ] )

			# set the reference info 
			srs = osr.SpatialReference()
			srs.ImportFromEPSG(4326)
			dst_ds.SetProjection( srs.ExportToWkt() )

			# write the band
			band = dst_ds.GetRasterBand(1)
			band.SetNoDataValue(nodata)
			band.WriteArray(data)
			dst_ds = None

		dt = "%s%02d00" %(ym,day)
		#self.process_highres_d02(dt)
		self.process_highres_d03(dt)
			
	def process_lowres(self):
		name					= "flood_14km"
		
		input_fname 			= "Flood_byStor_%s%02d00.bin" % (ym, day)
		input_fullname			= os.path.join(self.inpath, "gfms", ymd, input_fname)
		
		output_fname 			= "%s.%s%02d.tif" % (name, ym, day)
		output_fullname			= os.path.join(self.inpath, "gfms", ymd, output_fname)
		
		super_fname 			= "%s.%s%02d.x2.tif" % (name, ym, day)
		super_fullname			= os.path.join(self.inpath, "gfms", ymd, super_fname)

		geojson_fname 			= "%s.%s%02d.geojson" % (name, ym, day)
		geojson_fullname		= os.path.join(self.inpath, "gfms", ymd, geojson_fname)

		topojson_fname 			= "%s.%s%02d.topojson" % (name, ym, day)
		topojson_fullname		= os.path.join(self.inpath, "gfms", ymd, topojson_fname)
		topojson_fullname_gz	= topojson_fullname + ".gz"
		
		shp_gz_file				= os.path.join(self.inpath, "gfms", ymd, "%s.%s%02d.shp.gz" % (name, ym, day))
		shp_zip_file			= os.path.join(self.inpath, "gfms", ymd, "%s.%s%02d.shp.zip" % (name, ym, day))

		output_rgb_fname		= "%s.%s%02d_rgb.tif" % (name, ym, day)
		output_rgb_fullname		= os.path.join(self.inpath, "gfms", ymd, output_rgb_fname)
		color_file 				= os.path.join("cluts", "gfms_colors.txt")
		
		flood_dir				= os.path.join(self.inpath, "gfms", ymd)
		geojsonDir	= os.path.join(flood_dir,"geojson")
		if not os.path.exists(geojsonDir):
			os.makedirs(geojsonDir)

		levelsDir	= os.path.join(flood_dir,"levels")
		if not os.path.exists(levelsDir):
			os.makedirs(levelsDir)

		shpDir		= os.path.join(flood_dir, "shp")
		cmd = "rm -rf " + shpDir
		self.execute(cmd)
		
		merge_filename 			= os.path.join(geojsonDir, "%s_levels.geojson" % ymd)
		browse_filename 		= os.path.join(geojsonDir, "..", "%s_browse.tif" % ymd)
		browse_aux_filename 	= os.path.join(geojsonDir, "..", "%s_small_browse.tif.aux.xml" % ymd)
		subset_filename 		= os.path.join(geojsonDir, "..", "%s_small_browse.tif" % ymd)
		osm_bg_image			= os.path.join(geojsonDir, "..", "osm_bg.png")
		sw_osm_image			= os.path.join(geojsonDir, "..", "%s.%s%02d_thn.jpg" % (name,ym,day))

		x		= -127.25
		y		= 50
		res		= 0.125

		if self.force or not os.path.exists(output_fullname):
			rows 	= 800 
			cols	= 2458
			size	= rows*cols
			
			if verbose:
				print "gfms processing:", input_fullname
			
			fd		= open(input_fullname, 'rb')
			shape	= (rows, cols)
			data 	= numpy.fromfile(file=fd,dtype=numpy.float32, count=size).reshape(shape)
			
			data [data<0] = 0	#PGC
			
			#print "stats:", data.size, data.min(), data.mean(), data.max(), data.std()
			
		
			# Create gtif
			driver = gdal.GetDriverByName("GTiff")
			#dst_ds = driver.Create(output_fullname, cols, rows, 1, gdal.GDT_Float32)
			dst_ds = driver.Create(output_fullname, cols, rows, 1, gdal.GDT_Byte)
			# top left x, w-e pixel resolution, rotation, top left y, rotation, n-s pixel resolution
			dst_ds.SetGeoTransform( [ x, res, 0, y, 0, -res ] )

			# set the reference info 
			srs = osr.SpatialReference()
			srs.ImportFromEPSG(4326)
			dst_ds.SetProjection( srs.ExportToWkt() )

			# write the band
			band = dst_ds.GetRasterBand(1)
			#band.SetNoDataValue(-9999)
			band.WriteArray(data)
			dst_ds = None
		
		# Supersample it
		if self.force or not os.path.exists(super_fullname):			
			cmd = "gdalwarp -overwrite -q -tr %f %f -r cubicspline %s %s" % (res/10,res/10,output_fullname,super_fullname)
			self.execute(cmd)
		
		# Create RGB
		if self.verbose and (self.force or not os.path.exists(output_rgb_fullname)):		
			cmd = "gdaldem color-relief -q -alpha "+ output_fullname + " " + color_file + " " + output_rgb_fullname
			self.execute(cmd)
		
		# json
		#if self.force or not os.path.exists(geojson_fullname):			
		#	cmd = "makesurface vectorize --classfile gmfs_classes.csv --outfile %s --outvar flood %s " %( geojson_fullname, super_fullname)
		#	self.execute(cmd)

		# topojson
		#if self.force or not os.path.exists(topojson_fullname):
		#	cmd = "topojson --simplify-proportion 0.75  --bbox -p risk -o %s -- flood_24hr_forecast=%s" % (topojson_fullname, geojson_fullname ) 
		#	self.execute(cmd)

		#if self.force or not os.path.exists(topojson_fullname_gz):
		#	cmd = "gzip --keep %s" % (topojson_fullname)
		#	self.execute(cmd)
		
		levels 			= [ 200, 		100, 		50, 		20, 		10, 		5]
		hexColors 		= [ "#FF0000",  "#FFA500", "#FFD700", 	"#0000FF", "#00BFFF", 	"#00FF00" ]
		
		ds 				= gdal.Open( super_fullname )
		band			= ds.GetRasterBand(1)
		data			= band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize )
	
		if self.force or not os.path.exists(topojson_fullname+".gz"):
			for l in levels:
				fileName 		= os.path.join(levelsDir, ymd+"_level_%d.tif"%l)
				CreateLevel(l, geojsonDir, fileName, ds, data, "flood", force, verbose)
	
			jsonDict = dict(type='FeatureCollection', features=[])
	
			for l in reversed(levels):
				fileName 		= os.path.join(geojsonDir, "flood_level_%d.geojson"%l)
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
			cmd 	= "topojson -p -o "+ topojson_fullname + " " + merge_filename
			self.execute(cmd)

			if verbose:
				cmd 	= "gzip --keep "+ topojson_fullname
			else:
				cmd 	= "gzip "+ topojson_fullname
				
			self.execute(cmd)

		cmd= "ogr2ogr -f 'ESRI Shapefile' %s %s" % ( shpDir, merge_filename)
		self.execute(cmd)
	
		if force or not os.path.exists(shp_zip_file):
			mydir	= os.path.join(self.inpath, "gfms", ymd)
			#cmd 	= "cd %s; tar -cvzf %s shp" %(mydir, shp_gz_file)
			cmd 	= "cd %s; zip %s shp/*" %(mydir, shp_zip_file)
			self.execute(cmd)
			
		if self.force or not os.path.exists(sw_osm_image):
			MakeBrowseImage(ds, browse_filename, subset_filename, osm_bg_image, sw_osm_image, levels, hexColors, force, verbose, zoom=2)
			
		file_list = [ sw_osm_image, topojson_fullname_gz, shp_zip_file, output_fullname ]
		CopyToS3( s3_bucket, s3_folder, file_list, force, verbose )

		if not self.verbose:
			cmd = "rm -rf %s %s %s %s %s %s %s %s %s %s" % ( browse_filename, input_fullname, subset_filename, super_fullname, output_rgb_fullname, osm_bg_image, browse_aux_filename, levelsDir, geojsonDir, shpDir )
			print cmd
			self.execute(cmd)
			
# ======================================================================
# Make sure directories exist
#
def checkdirs():
	# required directories
	gmfs_dir		=  os.path.join(config.data_dir, "gfms", ymd)
				
	if not os.path.exists(gmfs_dir):
	    os.makedirs(gmfs_dir)
#
# ======================================================================
#
if __name__ == '__main__':
	version_num = int(gdal.VersionInfo('VERSION_NUM'))
	if version_num < 1800: # because of GetGeoTransform(can_return_null)
		print('ERROR: Python bindings of GDAL 1.8.0 or later required')
		sys.exit(1)
	
	parser 		= argparse.ArgumentParser(description='GFMS Processing')
	apg_input 	= parser.add_argument_group('Input')
	
	apg_input.add_argument("-f", "--force", action='store_true', help="forces new product to be generated")
	apg_input.add_argument("-v", "--verbose", action='store_true', help="Verbose Flag")
	apg_input.add_argument("-d", "--date", help="Date 2015-03-20 or today if not defined")
	
	options 	= parser.parse_args()
	todaystr	= date.today().strftime("%Y-%m-%d")

	force		= options.force
	verbose		= options.verbose
	dt			= options.date or todaystr

	today		= parse(dt)
	year		= today.year
	month		= today.month
	day			= today.day
	doy			= today.strftime('%j')
	ym	 		= "%d%02d" % (year, month)
	ymd 		= "%d%02d%02d" % (year, month, day)

	s3_folder	= os.path.join("gfms", str(year), doy)
	s3_bucket	= config.GLOBAL_BUCKET
	
	# Destination Directory
	dir			= config.data_dir
	checkdirs();
	
	app 		= GFMS( dir, force, verbose  )
	
	app.get_latest_file()
	app.process_lowres()
	#app.get_latest_highres_file()
	#app.process_highres()