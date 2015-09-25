// Pat Cappelaere
//
// Merge the trmm daily accumulation level files into one file, convert it to topojson and compress it
//
// node trmm_merge d03 20141118

var fs 			= require('fs');
var path		= require('path');
var exec 		= require('child_process').exec;
var zlib 		= require('zlib');

var gzip 		= zlib.createGzip();

var region		= process.argv[2]
var ymd	 		= process.argv[3]

var data_dir 	= "/home/workshop/ojo-processing/data"
var dir 		= path.join(data_dir, "trmm",region, ymd)

console.log("trmm merging of ", dir)

function ReadFile( filename) {
	var data	= fs.readFileSync(filename)
	var json	= JSON.parse(data)
	return json
}

var levels 	= [1,2,3,5,8,13,21,34,55,89,144]
var files 	= []
	
for( var l in levels) {
	var lev 		= levels[l]
	var filename	= path.join(dir, "geojson", "daily_precipitation_"+lev+".geojson")
	files.push(filename)
}

var merge_filename 		= path.join(dir, "geojson", "trmm_levels.geojson")
var topojson_filename 	= path.join(dir, "trmm_24." +  ymd + ".topojson")
var topojsongz_filename	= path.join(dir, "trmm_24." +  ymd + ".topojson.gz")

// Process first file
var json1 				= ReadFile( files.shift())
	
function AddFeatures( filename ) {
	var js = ReadFile( filename)
	for( var f in js.features ) {
		var feature = js.features[f]
		//console.log(feature)
		json1.features.push(feature)
	}
	//console.log(filename, "features:", json1.features.length)
}

for( var f in files) {
	AddFeatures(files[f])
}

//console.log("features:", json1.features.length)

var str = JSON.stringify(json1)
fs.writeFileSync(merge_filename, str)
console.log("wrote", merge_filename, " with features:", json1.features.length)

var cmd 	= "topojson -p -o "+ topojson_filename + " " + merge_filename
var child 	= exec(cmd, function(error, stdout, stderr) {
	console.log('stdout: ' + stdout);
	console.log('stderr: ' + stderr);
	if (error !== null) {
		console.log('exec error: ' + error);
	} else {
		var inp = fs.createReadStream(topojson_filename);
		var out = fs.createWriteStream(topojsongz_filename);

		inp.pipe(gzip).pipe(out);	
	}
})

