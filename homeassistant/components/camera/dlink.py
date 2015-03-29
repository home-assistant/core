import mimetypes
import requests
import logging

from homeassistant.components.camera import Camera

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    try:
        # base_url = config.get('vera_controller_url')
        # if not base_url:
        #     _LOGGER.error("The required parameter 'vera_controller_url' was not found in config")
        #     return False

        # device_data_str = config.get('device_data')        
        # device_data = None
        # if device_data_str:
        #     try:
        #         device_data = json.loads(device_data_str)
        #     except Exception as json_ex:
        #         _LOGGER.error('Vera lights error parsing device info, should be in the format [{"id" : 12, "name": "Lounge Light"}]: %s', json_ex)

        # controller = veraApi.VeraController(base_url)
        # devices = controller.get_devices('Switch')

        cameras = [DlinkCamera(hass, '', '', ''), DlinkCamera(hass, '', '', '')]
        # for device in devices:
        #     if is_switch_a_light(device_data, device.deviceId):
        #         lights.append(VeraLight(device, get_extra_device_data(device_data, device.deviceId)))

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
