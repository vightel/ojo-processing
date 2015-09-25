Workshop Training
=======================

You will learn:
- How to generate various products from NASA sources (and others) and store them on the cloud (AWS S3).
- Use the Open GeoSocial API for data distribution, visualization, discovery and sharing via social netowrks

Notes: This is not authoritative but work in progress used for capacity building and examples... This is not operational software!

Algorithms have not been formally validated by the science team!

Please become a collaborator and help us improve this repository.

### Copyright

Copyright © 2013  United States Government as represented by the Administrator of the National Aeronautics and Space Administration.  All Other Rights Reserved

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

## Pre-Requisites Prior To Workshop

* [Watch Presentation and Screencast Video](https://github.com/vightel/FloodMapsWorkshop/blob/master/FloodMappingWorkshop.pptx)

* Account on GitHub.com
  * You will have to send us your handle so we can add you as a collaborator on this project

* install git on your local machine, if not already installed

* Account on Amazon AWS [you may need a credit card] http://aws.amazon.com/  but it ought to be free for demo
	You will need to create an S3 bucket in a specific region

	You will need to get and set these environment variables
	AWS_SECRETACCESSKEY
	AWS_REGION
	AWS_ACCESSKEYID
	
* Account on Heroku
	If you do not have a development account on Heroku, create one and sign in
	Download the heroku toolbelt https://toolbelt.heroku.com/
	
* Developer Account on Mapbox to have access to Mapbox: https://www.mapbox.com/developers/
	and create a colorful map for you to use

* Laptop with: 
  * pgAdmin or Navicat (prefered http://www.navicat.com/download/navicat-for-postgresql ) to configure database 
  * [git](http://git-scm.com/downloads)
  * Editor ( [TextMate](http://macromates.com/), OSX XCode, [Eclipse](https://www.eclipse.org/), [VIM](http://www.vim.org/)...)
  
* Developer Account on Facebook https://developers.facebook.com/
	You will need to get and set these environment variables
	FACEBOOK_PROFILE_ID
	FACEBOOK_APP_SECRET
	FACEBOOK_APP_ID

* Developer Account on Twitter https://developers.facebook.com/
	You will need to get and set these environment variables
	TWITTER_CREATOR_ID
	TWITTER_DOMAIN
	TWITTER_SITE
	TWITTER_SITE_ID
	TWITTER_CREATOR

* Download docker and install: https://www.docker.com/
	Read documentation and get familiar with the concepts

    
## Workshop Part 1: ojo-processing

### Setup

Create a development directory for the workshop and download the code repository

```bash
$ mkdir ~/Development/worshop
$ git clone https://github.com/vightel/ojo-processing.git
$ cd ojo-processing
$ export WORKSHOP_DIR=~/Development/worshop/ojo-processing
```

* Create an Heroku Instance and a small Postgres database.  We will use an enhanced builpack used for later and remember your heroku app name

```bash
$ cp buildpacks .buildpacks
$ heroku login

$ heroku create
	Creating stark-sands-3006... done, stack is cedar-14
	https://stark-sands-3006.herokuapp.com/ | https://git.heroku.com/stark-sands-3006.git

$ heroku addons:create heroku-postgresql:hobby-dev --app stark-sands-3006
	Creating postgresql-spherical-2968... done, (free)
	Adding postgresql-spherical-2968 to stark-sands-3006... done
	Setting DATABASE_URL and restarting stark-sands-3006... done, v3
	Database has been created and is available

$ heroku config -s --app stark-sands-3006
```

* Configure your environment with your own settings and DATABASE_URL.  You will need to parse that URL and set the individual database environment variables as well.

```bash
$ cp dockerignore .dockerignore
$ cp envs.copy.sh envs.docker.sh
$ vi envs.docker.sh
```

### Create Processing Container

Create a new Docker VM if you have never done so

```bash
$ docker-machine create --driver virtualbox default
$ docker-machine env default
$ eval "$(docker-machine env default)"
```

Build container image from provided docker file

```bash
$ docker build -t ojo-processing .
```

Now we can run and test the image

```bash
$ export DATAFOLDER="-v /Users/patricecappelaere/Development/workshop/ojo-processing:/home/workshop/ojo-processing"
$ docker run $DATAFOLDER --name ojo-processing -it --rm ojo-processing /bin/bash -login
```
Within that new shell, you can check:
```bash
$ gdalinfo --version
	GDAL 2.0.0, released 2015/06/14
$ ogrinfo --formats
$ cd $WORKSHOP_DIR/python
$ python check_environment.py
```	
### Landslide Nowcast Processing

You need to edit the python/config.py with your own AWS S3 bucket name for your region.
Then run the processing script to generate the landslide nowcast for a particular day.
The first time around, it will need to generate the last 60 days of precipitation.

Notes: 

Central America is region d02 as defined in config.py

Python scripts can be run with -v option for verbose and -f to force the regeneration of products
Make sure that you have the right envs for accessing your AWS S3 bucket (and it is public)

```bash
$ python landslide_nowcast.py --region d02 --date 2015-09-23 -v
```	
### TRMM data (already done in Landslide nowcast
```bash
python ./trmm_process.py --region d02 --date 2015-09-23
```	

### Quakes from USGS
```bash
python ./quake.py --region d02 --date 2015-09-23
```	

### MODIS BURNED AREAS from MODIS
```bash
python ./modis-burnedareas.py --region d02 --date 2015-09-23
```	

### MODIS ACTIVE FIRES from MODIS  - PROBLEM with node
```bash
python ./modis-active-fires.py --region d02 --date 2015-09-23
```	

### GPM Global, 1-d, 3-d and 7-d products
```bash
python ./gpm_global.py  --date 2015-09-22
```	

### GEOS5 Global
```bash
python ./geos5.py  --date 2015-09-23
```	

### GPM Global
```bash
python ./gpm_global.py  --date 2015-09-22
```	

### GFMS Global
```bash
python ./gfms_vectorizer.py  --date %s 2015-09-23
```	

## NOTES
$ docker ps -a
$ docker images
$ docker inspect

Cleanup stopped containers and dangling images
$ docker rm -v $(docker ps -aq )
$ docker rmi $(docker images -f dangling=true -q)