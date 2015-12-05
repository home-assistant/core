"""
homeassistant.components.light.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera/
"""
import logging
import time

from requests.exceptions import RequestException
from homeassistant.components.switch.vera import VeraSwitch

from homeassistant.components.light import ATTR_BRIGHTNESS

REQUIREMENTS = ['https://github.com/pavoni/home-assistant-vera-api/archive/'
                'efdba4e63d58a30bc9b36d9e01e69858af9130b8.zip'
                '#python-vera==0.1.1']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """
    import pyvera as veraApi

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    controller = veraApi.VeraController(base_url)
    devices = []
    try:
        devices = controller.get_devices([
            'Switch',
            'On/Off Switch',
            'Dimmable Switch'])
    except RequestException:
        # There was a network related error connecting to the vera controller
        _LOGGER.exception("Error communicating with Vera API")
        return False

    lights = []
    for device in devices:
        extra_data = device_data.get(device.deviceId, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            lights.append(VeraLight(device, extra_data))

    add_devices_callback(lights)


class VeraLight(VeraSwitch):
    """ Represents a Vera Light, including dimmable. """

    @property
    def state_attributes(self):
        attr = super().state_attributes or {}

        if self.vera_device.is_dimmable:
            attr[ATTR_BRIGHTNESS] = self.vera_device.get_brightness()

        return attr

    def turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self.last_command_send = time.time()
        self.is_on_status = True
