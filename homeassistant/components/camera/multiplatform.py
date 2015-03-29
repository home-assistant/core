""" 
Support for IP Cameras.

This file is a helper for supporting multiple platforms(camera types) simultaneously and may be 
deprecated in the future if the config file format if multi-platform per domain support is added.

Configuration:
The configuration will help the component to load the specific functionality for a particular model
of IP Camera.  At the top level is "brand", followed by "family" and then "model".  The logic for 
loading a particular device is as follows:

brand found?
No: load up the generic camera class
Yes: Try and find the specific model for that brand

model found?
No: try and find a device that matched brand and family
Yes: load up the device specific to that model

family found?
No: load up the generic camera class for the brand
Yes: load up the generic class for the family

NOTE: if you are using an unsupported device you can at least get basic functionality by specifying
the still_image_url

To use this component you will need to add something like the following to your config/configuration.yaml

camera:
    platform: multiplatform    
    device_data: 
        - 
            base_url: http://YOUR_CAMERA_IP_AND_PORT/
            name: Door Camera
            brand: dlink
            family: DCS
            model: DCS-930L
            username: YOUR_USERNAME
            password: YOUR_PASSWORD
        -
            base_url: http://YOUR_CAMERA_IP_AND_PORT/
            name: Balcony Camera
            brand: Acme
            model: generic
            still_image_url: image.jpg
            username: YOUR_USERNAME
            password: YOUR_PASSWORD            

VARIABLES: 

device_data
*Required
This is the base URL of your IP Camera including the port number if not running on 80



device_data
*Required
This contains an array of all your configured cameras


These are the variables for the device_data array:

base_url
*Required
The base URL for accessing you camera
Example: http://192.168.1.21:2112/

name
*Optional
This parameter allows you to override the name of your camera in homeassistant


brand
*Optional
The manufacturer of your device, used to help load the specific camera functionality.

family
*Optional
The family of devices by the specified brand, useful when many models support the same
settings.  THis used when attempting load up specific device functionality.

model
*Optional
The specific model number of your device.

still_image_url
*Optional
Useful if using an unsupported camera model.  This should point to the location of the 
still image on your particular camera and should be relative to your specified base_url.
Example: cam/image.jpg

username
*Required
THe username for acessing your camera

password
*Required
the password for accessing your camera


"""

import mimetypes
import requests
import logging
import json

from homeassistant.loader import get_component

from homeassistant.components.camera import (DOMAIN, ENTITY_ID_FORMAT)

from homeassistant.components.camera import Camera
#from homeassistant.components.camera.dlink import DlinkCamera

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):    
    #try:
    
    device_data = config.get('device_data')

    cameras = []
    if device_data:                        
        for device in device_data:
            platform = None
            if device.get('brand'):
                try:
                    platform = get_component(ENTITY_ID_FORMAT.format(device.get('brand')))
                except Exception as inst:
                    _LOGGER.warning("Could not find camera component for brand %s: %s", device.get('brand'), inst)

            #cameras.append(Camera(hass, device))
            if platform is not None:
                #cameras.append(DlinkCamera(hass, device))
                cam = platform.get_camera(hass, device)
                if cam is not None:
                    cameras.append(cam)
            else:
                cameras.append(Camera(hass, device))

    add_devices_callback(cameras)
    # except Exception as inst:
    #     _LOGGER.error("Could not find cameras: %s", inst)
    #     return False
