"""
homeassistant.components.light.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera lights. This component is useful if you wish for switches
connected to your Vera controller to appear as lights in Home Assistant.
All switches will be added as a light unless you exclude them in the config.

Configuration:

To use the Vera lights you will need to add something like the following to
your configuration.yaml file.

light:
  platform: vera
  vera_controller_url: http://YOUR_VERA_IP:3480/
  device_data:
    12:
      name: My awesome switch
      exclude: true
    13:
      name: Another switch

Variables:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80. Example: http://192.168.1.21:3480/

device_data
*Optional
This contains an array additional device info for your Vera devices. It is not
required and if not specified all lights configured in your Vera controller
will be added with default values. You should use the id of your vera device
as the key for the device within device_data.

These are the variables for the device_data array:

name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used.

exclude
*Optional
This parameter allows you to exclude the specified device from Home Assistant,
it should be set to "true" if you want this device excluded.

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
