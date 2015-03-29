"""
homeassistant.components.camera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Component to interface with various cameras that can be monitored.
"""
import mimetypes
import requests
import logging
from datetime import timedelta
import re

#import Image

from homeassistant.loader import get_component
import homeassistant.util as util
from homeassistant.const import (
    STATE_OPEN)
from homeassistant.helpers import (
    platform_devices_from_config)
from homeassistant.components import group, discovery, wink
from homeassistant.helpers import Device

from homeassistant.helpers import (
    generate_entity_id, extract_entity_ids, config_per_platform)

DOMAIN = 'camera'
DEPENDENCIES = []

GROUP_NAME_ALL_CAMERAS = 'all_cameras'
ENTITY_ID_ALL_CAMERAS = group.ENTITY_ID_FORMAT.format(
    GROUP_NAME_ALL_CAMERAS)

ENTITY_ID_FORMAT = DOMAIN + '.{}'

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=1)

# Maps discovered services to their platforms
DISCOVERY_PLATFORMS = {
}

_LOGGER = logging.getLogger(__name__)

CAMERA_HTTP_PROXY_REGISTERED = False

def is_on(hass, entity_id=None):
    """ Returns if the camera is open based on the statemachine. """
    entity_id = entity_id or ENTITY_ID_ALL_CAMERAS

    return hass.states.is_state(entity_id, STATE_OPEN)



def setup(hass, config):
    """ Track states and offer events for cameras. """
    logger = logging.getLogger(__name__)

    

    # cameras = platform_devices_from_config(
    #     config, DOMAIN, hass, ENTITY_ID_FORMAT, logger)    
    
    cameras = {}

    # Track all cameras in a group
    camera_group = group.Group(
        hass, GROUP_NAME_ALL_CAMERAS, cameras.keys(), False)




    def add_cameras(new_cameras):
        """ Add cameras to the component to track. """
        for camera in new_cameras:
            if camera is not None and camera not in cameras.values():

                camera.hass = hass
                camera.entity_id = generate_entity_id(
                    ENTITY_ID_FORMAT, camera.name, cameras.keys())

                cameras[camera.entity_id] = camera

                camera.update_ha_state()

        camera_group.update_tracked_entity_ids(cameras.keys())

    for p_type, p_config in config_per_platform(config, DOMAIN, _LOGGER):
        platform = get_component(ENTITY_ID_FORMAT.format(p_type))

        if platform is None:
            _LOGGER.error("Unknown type specified: %s", p_type)

    platform.setup_platform(hass, p_config, add_cameras)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS)
    def update_camera_states(now):
        """ Update states of all cameras. """
        global CAMERA_HTTP_PROXY_REGISTERED

        if CAMERA_HTTP_PROXY_REGISTERED is not True:
            # Register the handler for the camera image proxy
            if 'http' not in hass.components:
                _LOGGER.error('Dependency http is not loaded')
            else: 
                CAMERA_HTTP_PROXY_REGISTERED = True
                hass.http.register_path('GET', re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_image)
                _LOGGER.info("registered camera proxy http endpoint")

        if cameras:
            logger.info("Updating camera states")

            for camera in cameras.values():
                camera.update_ha_state()
    

    def _proxy_camera_image(handler, path_match, data):
        """ Proxies the camera image via the HA server. """
        entity_id = path_match.group('entity_id')
        
        camera = cameras.get(entity_id)
        response = camera.get_camera_image()
        handler.wfile.write(response.content)

    #check if we can register the http path yet
    
    if 'http' not in hass.components:
        _LOGGER.error('Dependency http is not loaded')
    else: 
        CAMERA_HTTP_PROXY_REGISTERED = True
        hass.http.register_path('GET', re.compile(r'/api/camera_proxy/(?P<entity_id>[a-zA-Z\._0-9]+)'), _proxy_camera_image)
        _LOGGER.info("registered camera proxy http endpoint")

    update_camera_states(None)

    # Fire every 10 seconds
    hass.track_time_change(update_camera_states, second=range(0, 60, 10))

    return True



class Camera(Device):
    """ Base class for cameras. """

    def __init__(self, hass, device_info):
        #super().__init__(hass, device_info)
        self.device_info = device_info
        self.BASE_URL = device_info.get('base_url')
        if not self.BASE_URL.endswith('/'):
            self.BASE_URL = self.BASE_URL + '/'
        self.username = device_info.get('username')
        self.password = device_info.get('password')

    def get_camera_image(self):        
        response = requests.get(self.still_image_url, auth=(self.username, self.password))        
        return response

    @property
    def name(self):
        if self.device_info.get('name'): 
            return self.device_info.get('name')
        else:
            return super().name


    @property
    def state_attributes(self):
        attr = super().state_attributes       
        attr['entity_picture'] = '/api/camera_proxy/' + self.entity_id
        """ Returns optional state attributes. """
        return attr

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        if self.device_info.get('still_image_url'):
            return self.BASE_URL + self.device_info.get('still_image_url')
        return self.BASE_URL + 'image.jpg'
