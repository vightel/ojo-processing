#
# Processes TRMM Data for a specific region
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
ftp_site 	= "jsimpson.pps.eosdis.nasa.gov"
#gis_path 	= "pub/merged/3B42RT/"
gis_path 	= "data/imerg/gis/"

def execute( cmd ):
	if verbose:
		print cmd
	os.system(cmd)

#def CreateLevel(maxl, minl, geojsonDir, fileName, src_ds, data, attr):
def CreateLevel(l, geojsonDir, fileName, src_ds, data, attr):
	global force, verbose
		
	minl				= l
	projection  		= src_ds.GetProjection()
	geotransform		= src_ds.GetGeoTransform()
	#band				= src_ds.GetRasterBand(1)
		
	xorg				= geotransform[0]
	yorg  				= geotransform[3]
	pres				= geotransform[1]
	xmax				= xorg + geotransform[1]* src_ds.RasterXSize
	ymax				= yorg - geotransform[1]* src_ds.RasterYSize


	if not force and os.path.exists(fileName):
		return
		
	driver 				= gdal.GetDriverByName( "GTiff" )

	dst_ds_dataset		= driver.Create( fileName, src_ds.RasterXSize, src_ds.RasterYSize, 1, gdal.GDT_Byte, [ 'COMPRESS=DEFLATE' ] )
	dst_ds_dataset.SetGeoTransform( geotransform )
	dst_ds_dataset.SetProjection( projection )
	o_band		 		= dst_ds_dataset.GetRasterBand(1)
	o_data				= o_band.ReadAsArray(0, 0, dst_ds_dataset.RasterXSize, dst_ds_dataset.RasterYSize )
	
	#o_data.fill(255)
	#o_data[data>=maxl] 	= 0
	#o_data[data<minl]	= 0
	
	o_data[data>=l]		= 255
	o_data[data<l]		= 0

	count 				= (o_data > 0).sum()	
	if verbose:
		print "Level", minl, " count:", count

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

		#cmd = str.format("node set_geojson_property.js --file {0} --prop frost={1}", fileName+".geojson", frost)
		#execute(cmd)
	
		#cmd = str.format("topojson -o {0} --simplify-proportion 0.5 -p {3}={1} -- {3}={2}", fileName+".topojson", l, fileName+".geojson", attr ); 
		cmd = str.format("topojson --bbox --simplify-proportion 0.5 -o {0} --no-stitch-poles -p {3}={1} -- {3}={2}", fileName+".topojson", minl, fileName+".geojson", attr ); 
		execute(cmd)
	
		# convert it back to json
		cmd = "topojson-geojson --precision 4 -o %s %s" % ( geojsonDir, fileName+".topojson" )
		execute(cmd)
	
		# rename file
		output_file = "%s_level_%d.geojson" % (attr, minl)
		json_file	= "%s.json" % attr
		cmd 		= "mv %s %s" % (os.path.join(geojsonDir,json_file), os.path.join(geojsonDir, output_file))
		execute(cmd)
		
		
def get_daily_gpm_files(trmm_gis_files, mydir, year, month):
	global force, verbose
	
	filepath = gis_path+ "%02d" % ( month)
	
	if verbose:
		print("Checking "+ftp_site+"/" + filepath + " for latest file...")
	
	try:
		ftp = FTP(ftp_site)
	
		ftp.login('pat@cappelaere.com','pat@cappelaere.com')               					# user anonymous, passwd anonymous@
		ftp.cwd(filepath)
	
	except Exception as e:
		print "FTP login Error", sys.exc_info()[0], e
		print "Exception", e
		sys.exit(-1)

	for f in trmm_gis_files:
		if verbose:
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
				print "GPM IMERG FTP Error", sys.exc_info()[0], e					
				os.remove(local_filename)
				ftp.close();
				sys.exit(-2)

	ftp.close()
	
def save_tif(fname, data, ds, type, colors):
	if verbose:
		print "saving", fname
		
	format 		= "GTiff"
	driver 		= gdal.GetDriverByName( format )
	dst_ds	 	= driver.Create( fname, ds.RasterXSize, ds.RasterYSize, 1, type, [ 'COMPRESS=DEFLATE' ] )
	band 		= dst_ds.GetRasterBand(1)
	
	band.WriteArray( data )
	
	dst_ds.SetGeoTransform( ds.GetGeoTransform() )
	dst_ds.SetProjection( ds.GetProjection() )
	
	ct = gdal.ColorTable()
	ct.SetColorEntry( 0, (0, 0, 0, 0) )
	ct.SetColorEntry( 1, (255, 0, 0, 255) )
	band.SetRasterColorTable(ct)
	
	dst_ds = None
			
def process(gpm_dir, name, gis_file_day, ymd ):
	global force, verbose

	regionName = 'global'
	
	region_dir	= os.path.join(gpm_dir,regionName)
	if not os.path.exists(region_dir):            
		os.makedirs(region_dir)
	
	origFileName 		= os.path.join(gpm_dir,gis_file_day)
	ds 					= gdal.Open(origFileName)
	geotransform		= ds.GetGeoTransform()

	xorg				= geotransform[0]
	yorg  				= geotransform[3]
	pixelsize			= geotransform[1]
	xmax				= xorg + geotransform[1]* ds.RasterXSize
	ymax				= yorg - geotransform[1]* ds.RasterYSize
	
	bbox				= [xorg, ymax, xmax, yorg]
	
	supersampled_file	= os.path.join(region_dir, "%s.%s_x2.tif" % (name, ymd))

	if force or not os.path.exists(supersampled_file):
		cmd 			= "gdalwarp -overwrite -q -tr %f %f -te %f %f %f %f -r cubicspline -co COMPRESS=LZW %s %s"%(pixelsize/2, pixelsize/2, bbox[0], bbox[1], bbox[2], bbox[3], origFileName, supersampled_file)
		execute(cmd)
	
	geojsonDir	= os.path.join(region_dir,"geojson_%s" % (name))
	if not os.path.exists(geojsonDir):            
		os.makedirs(geojsonDir)

	levelsDir	= os.path.join(region_dir,"levels_%s" % (name))
	if not os.path.exists(levelsDir):            
		os.makedirs(levelsDir)

	shpDir	= os.path.join(region_dir,"shp_%s" % (name))
	cmd 	= "rm -rf " + shpDir
	execute(cmd)
	os.makedirs(shpDir)

	merge_filename 		= os.path.join(geojsonDir, "%s.%s.geojson" % (name, ymd))
	topojson_filename 	= os.path.join(geojsonDir, "..", "%s.%s.topojson" % (name,ymd))
	browse_filename 	= os.path.join(geojsonDir, "..", "%s.%s_browse.tif" % (name,ymd))
	subset_aux_filename = os.path.join(geojsonDir, "..", "%s.%s_small_browse.tif.aux.xml" % (name, ymd))
	subset_filename 	= os.path.join(geojsonDir, "..", "%s.%s_small_browse.tif" % (name, ymd))
	
	#osm_bg_image		= os.path.join(geojsonDir, "..", "osm_bg.png")	
	osm_bg_image		= os.path.join(config.data_dir, "gpm", "osm_bg.png")
	
	sw_osm_image		= os.path.join(geojsonDir, "..", "%s.%s_thn.jpg" % (name, ymd))
	tif_image			= os.path.join(geojsonDir, "..", "%s.%s.tif" % (name, ymd))

	geojson_filename 	= os.path.join(geojsonDir, "..", "%s.%s.json" % (name,ymd))
	shapefile_gz		= os.path.join(geojsonDir, "..", "%s.shp.gz" % name)
	shp_zip_file		= os.path.join(geojsonDir, "..", "%s.shp.zip" % name)

	levels 				= [377, 233, 144, 89, 55, 34, 21, 13, 8, 5, 3, 2]
		
	# http://hclwizard.org/hcl-color-scheme/
	# http://vis4.net/blog/posts/avoid-equidistant-hsv-colors/
	# from http://tristen.ca/hcl-picker/#/hlc/12/1/241824/55FEFF
	# Light to dark
	hexColors 			= [ "#56F6FC","#58DEEE","#5BC6DE","#5EAFCC","#5E99B8","#5D84A3","#596F8D","#535B77","#4A4861","#3F374B","#322737","#241824"]
	
	ds 					= gdal.Open( supersampled_file )
	band				= ds.GetRasterBand(1)
	data				= band.ReadAsArray(0, 0, ds.RasterXSize, ds.RasterYSize )

	sdata 				= data/10			# back to mm
	
	if force or not os.path.exists(topojson_filename+".gz"):
		for idx, l in enumerate(levels):
			print "level", idx
			#if idx < len(levels)-1:
			fileName 		= os.path.join(levelsDir, ymd+"_level_%d.tif"%l)
			#CreateLevel(l, levels[idx+1], geojsonDir, fileName, ds, sdata, "precip")
			CreateLevel(l, geojsonDir, fileName, ds, sdata, "precip")
	
		jsonDict = dict(type='FeatureCollection', features=[])
	
		for l in reversed(levels):
			fileName 		= os.path.join(geojsonDir, "precip_level_%d.geojson"%l)
			if os.path.exists(fileName):
				with open(fileName) as data_file:    
					jdata = json.load(data_file)
		
				if 'features' in jdata:
					for f in jdata['features']:
						jsonDict['features'].append(f)
	

		with open(merge_filename, 'w') as outfile:
		    json.dump(jsonDict, outfile)	

		# Convert to topojson
		cmd 	= "topojson --bbox -p precip -o "+ topojson_filename + " " + merge_filename
		execute(cmd)

		cmd 	= "gzip --keep "+ topojson_filename
		execute(cmd)
	
	# Convert to shapefile		
	if 1: #and os.path.exists(merge_filename):
		cmd= "ogr2ogr -f 'ESRI Shapefile' %s %s" % ( shpDir, merge_filename)
		execute(cmd)
	
	if force or not os.path.exists(shp_zip_file):
		#cmd 	= "cd %s; tar -cvzf %s shp" %(region_dir, shapefile_gz)
		cmd 	= "cd %s; zip %s shp_%s/*" %(region_dir, shp_zip_file, name)
		execute(cmd)
		
	# problem is that we need to scale it or adjust the levels for coloring (easier)
	adjusted_levels 		= [3770, 2330, 1440, 890, 550, 340, 210, 130, 80, 50, 30, 20]
	
	zoom = 1
	if force or not os.path.exists(sw_osm_image):
		MakeBrowseImage(ds, browse_filename, subset_filename, osm_bg_image, sw_osm_image, adjusted_levels, hexColors, force, verbose, zoom)
	
	if force or not os.path.exists(tif_image):
		cmd 				= "gdalwarp -overwrite -q -co COMPRESS=LZW %s %s"%( origFileName, tif_image)
		execute(cmd)
		
	ds = None
	
	file_list = [ sw_osm_image, topojson_filename+".gz", tif_image, shp_zip_file ]
	#CopyToS3( s3_bucket, s3_folder, file_list, force, verbose )
	CopyToS3( s3_bucket, s3_folder, file_list, 1, 1 )
	
	if not verbose: # Cleanup
		cmd = "rm -rf %s %s %s %s %s %s %s %s %s %s %s" % (origFileName, supersampled_file, merge_filename, topojson_filename, subset_aux_filename, browse_filename, subset_filename, osm_bg_image, geojsonDir, levelsDir, shpDir)
		execute(cmd)

# ===============================
# Main
#
# python gpm_global.py --date 2015-04-07 -v -f

if __name__ == '__main__':

	aws_access_key 			= os.environ.get('AWS_ACCESSKEYID')
	aws_secret_access_key 	= os.environ.get('AWS_SECRETACCESSKEY')
	assert(aws_access_key)
	assert(aws_secret_access_key)
	
	parser = argparse.ArgumentParser(description='Generate Daily Precipitation map')
	apg_input = parser.add_argument_group('Input')
	apg_input.add_argument("-f", "--force", action='store_true', help="HydroSHEDS forces new water image to be generated")
	apg_input.add_argument("-v", "--verbose", action='store_true', help="Verbose on/off")
	apg_input.add_argument("-d", "--date", help="Date 2015-03-20 or today if not defined")

	todaystr	= date.today().strftime("%Y-%m-%d")

	options 	= parser.parse_args()

	dt			= options.date or todaystr
	force		= options.force
	verbose		= options.verbose
	
	today		= parse(dt)
	year		= today.year
	month		= today.month
	day			= today.day
	doy			= today.strftime('%j')
	ymd 		= "%d%02d%02d" % (year, month, day)		

	gpm_dir	= os.path.join(config.data_dir, "gpm", str(year),doy)
	if not os.path.exists(gpm_dir):
	    os.makedirs(gpm_dir)
		
	s3_folder			= os.path.join("gpm", str(year), doy)
	s3_bucket			= config.GLOBAL_BUCKET
	
	gis_file_day		= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.1day.tif"%(year, month, day)
	gis_file_day_tfw 	= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.1day.tfw"%(year, month, day)

	gis_file_3day		= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.3day.tif"%(year, month, day)
	gis_file_3day_tfw 	= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.3day.tfw"%(year, month, day)

	gis_file_7day		= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.7day.tif"%(year, month, day)
	gis_file_7day_tfw 	= "3B-HHR-L.MS.MRG.3IMERG.%d%02d%02d-S233000-E235959.1410.V03E.7day.tfw"%(year, month, day)
	
	print gis_file_day
	files 				= [
		gis_file_day, gis_file_day_tfw, 
		gis_file_3day, gis_file_3day_tfw, 
		gis_file_7day, gis_file_7day_tfw
	]
	
	if force or not os.path.exists(os.path.join(gpm_dir,gis_file_day)):
		get_daily_gpm_files(files, gpm_dir, year, month)
	
	process(gpm_dir, "gpm_1d", gis_file_day, ymd)
	process(gpm_dir, "gpm_3d", gis_file_3day, ymd)
	process(gpm_dir, "gpm_7d", gis_file_7day, ymd)
	
	if not verbose:
		for f in files:
			cmd = "rm -rf %s" % (os.path.join(gpm_dir,f))
			execute(cmd)
