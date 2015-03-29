import logging
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import validate_config
from homeassistant.components.camera import DOMAIN
from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    try:        
        if not validate_config({DOMAIN: config},
                           {DOMAIN: ['base_url', CONF_USERNAME, CONF_PASSWORD]},
                           _LOGGER):
            return None

        cameras = [DlinkCamera(hass, config)]

        add_devices_callback(cameras)
    except Exception as inst:
        _LOGGER.error("Could not find cameras: %s", inst)
        return False

def get_camera(hass, device_info):
    return DlinkCamera(hass, device_info) 

class DlinkCamera(Camera):
    def __init__(self, hass, device_info):
        super().__init__(hass, device_info)

    @property
    def still_image_url(self):
        """ This should be implemented by different camera models. """
        return self.BASE_URL + 'image.jpg'
