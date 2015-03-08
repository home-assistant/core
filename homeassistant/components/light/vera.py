"""
Support for Vera lights.

Configuration:
This component is useful if you wish for switches connected to your Vera
controller to appear as lights in homeassistant.  All switches will be added
as a light unless you exclude them in the config.

To use the Vera lights you will need to add something like the following to
your config/configuration.yaml

light:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        -
            vera_id: 12
            name: My awesome switch
            exclude: true
        -
            vera_id: 13
            name: Another switch

VARIABLES:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80
Example: http://192.168.1.21:3480/


device_data
*Optional
This contains an array additional device info for your Vera devices.  It is not
required and if not specified all lights configured in your Vera controller
will be added with default values.


These are the variables for the device_data array:

vera_id
*Required
The Vera device id you wish these configuration options to be applied to


name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used


exclude
*Optional
This parameter allows you to exclude the specified device from homeassistant,
it should be set to "true" if you want this device excluded

"""
import logging
from homeassistant.components.switch.vera import VeraSwitch
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.vera.vera as veraApi

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Vera lights. """

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', None)

    controller = veraApi.VeraController(base_url)
    devices = []
    try:
        devices = controller.get_devices('Switch')
    except IOError as inst:
        # There was a network related error connecting to the vera controller
        _LOGGER.error("Could not find Vera lights: %s", inst)
        return False

    lights = []
    for device in devices:
        extra_data = get_extra_device_data(device_data, device.deviceId)
        exclude = False
        if extra_data:
            exclude = extra_data.get('exclude', False)

        if exclude is not True:
            lights.append(VeraSwitch(device, extra_data))

    add_devices_callback(lights)


def get_extra_device_data(device_data, device_id):
    """ Gets the additional configuration data by Vera device Id """
    if not device_data:
        return None

    for item in device_data:
        if item.get('vera_id') == device_id:
            return item

    return None
