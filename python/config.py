import os
#
# Directories setup
#
DATA_DIR			= os.environ['WORKSHOP_DIR'] + "/data"
PYTHON_DIR			= os.environ['WORKSHOP_DIR'] + "/python"

# For compatibility
data_dir			= DATA_DIR	

# S3 bucket to store data and publish it
GLOBAL_BUCKET		= "ojo-workshop"

#
# UPDATE BUCKETS FOR EVERY REGION YOU ARE PROCESSING
#
regions		= {
	'd02': {
		'name':			"Central America",
		'bbox': 		[-92.6833333,   6.1666667, -75.8500000,  19.0833333],
		'centerlat':	12.625,
		'centerlon':	-84.26666665,
		'pixelsize':	0.008333333333330,
		'columns': 		2020,
		'rows': 		1550,
		'thn_width':	389,
		'thn_height':	298,
		'thn_zoom': 	5,
		'bucket':		"ojo-workshop",
		'thn_zoom': 	5,
		'tiles-zoom':	"6-14",
		'modis-win': 	"Win04"		# MCD45 Window (MODIS Burned Areas)
	},
	'd03': {
		'name':			"Hispaniola",
		'bbox': 		[-74.9416667, 16.3500000, -64.9750000,  21.4250000],
		'bucket':		"ojo-d3",
		'thn_zoom': 	6
	},
	'd04': {
		'name':			"Namibia",
		'bbox': 		[18, -21, 26, -17 ],
		'bucket':		"ojo-d4",
		'thn_zoom': 	6
	},
	'd05': {
		'name':			"Malawi",
		'bbox': 		[32.717, -17.150, 37.0, -5 ],
		'bucket':		"ojo-d5",
		'thn_zoom': 	6
	},
	'd06': {
		'name':			"Pakistan",
		'bbox': 		[60, 20, 80, 40 ],
		'bucket':		"ojo-d6",
		'thn_zoom': 	6
	},
	'd07': {
		'name':			"East Africa",
		'bbox': 		[21.77, -12.27, 51.09, 23.95 ],
		'bucket':		"ojo-d7",
		'thn_zoom': 	5
	}
}
	
#
# Data Directories
#
# Simple ones first
TRMM_DIR					= os.path.join(DATA_DIR, "trmm")
GPM_DIR						= os.path.join(DATA_DIR, "gpm")
GFMS_DIR					= os.path.join(DATA_DIR, "gfms")
GEOS5_DIR					= os.path.join(DATA_DIR, "geos5")
MODIS_ACTIVE_FIRES_DIR		= os.path.join(DATA_DIR, "modis_af")
MODIS_BURNEDAREAS_DIR		= os.path.join(DATA_DIR, "modis_burnedareas")
QUAKES_DIR					= os.path.join(DATA_DIR, "quakes")
LANDSLIDE_NOWCAST_DIR		= os.path.join(DATA_DIR, "landslide_nowcast")
VHI_DIR						= os.path.join(DATA_DIR, "vhi")

