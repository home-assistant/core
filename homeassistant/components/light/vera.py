"""
homeassistant.components.light.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera.html
"""
import logging
from requests.exceptions import RequestException
from homeassistant.components.switch.vera import VeraSwitch

REQUIREMENTS = ['https://github.com/balloob/home-assistant-vera-api/archive/'
                'a8f823066ead6c7da6fb5e7abaf16fef62e63364.zip'
                '#python-vera==0.1']

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
        devices = controller.get_devices(['Switch', 'On/Off Switch'])
    except RequestException:
        # There was a network related error connecting to the vera controller
        _LOGGER.exception("Error communicating with Vera API")
        return False

    lights = []
    for device in devices:
        extra_data = device_data.get(device.deviceId, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            lights.append(VeraSwitch(device, extra_data))

    add_devices_callback(lights)
