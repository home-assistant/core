"""
Support for Razberry switches.

Configuration:
To use the Razberry lights you will need to add something like the following to
your config/configuration.yaml

switch:
    platform: razberry
    razberry_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        12:
            name: My awesome switch
            exclude: true
        13:
            name: Another Switch

VARIABLES:

razberry_controller_url
*Required
This is the base URL of your razberry controller including the port number if not
running on 80
Example: http://192.168.1.21:3480/


device_data
*Optional
This contains an array additional device info for your Razberry devices.  It is not
required and if not specified all lights configured in your Razberry controller
will be added with default values.  You should use the id of your razberry device
as the key for the device within device_data


These are the variables for the device_data array:


name
*Optional
This parameter allows you to override the name of your Razberry device in the HA
interface, if not specified the value configured for the device in your Razberry
will be used


exclude
*Optional
This parameter allows you to exclude the specified device from homeassistant,
it should be set to "true" if you want this device excluded

"""
import logging
import time
from requests.exceptions import RequestException
from homeassistant.helpers.entity import ToggleEntity
# pylint: disable=no-name-in-module, import-error
import homeassistant.external.razberry.razberry as razberryApi

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Razberry switches. """

    base_url = config.get('razberry_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'razberry_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    razberry_controller = razberryApi.RazberryController(base_url)
    devices = []
    try:
        devices = razberry_controller.get_devices()
    except RequestException:
        # There was a network related error connecting to the razberry controller
        _LOGGER.exception("Error communicating with Razberry API")
        return False

    razberry_switches = []
    for device in devices:
        extra_data = device_data.get(int(device.deviceId), {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True and int(device.instanceId) > 0:
            if (not extra_data[int(device.instanceId)]) or (extra_data[int(device.instanceId)].get('exclude', False) is not True):
                razberry_switches.append(RazberrySwitch(device, extra_data))

    return razberry_switches


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Razberry lights. """
    add_devices(get_devices(hass, config))


class RazberrySwitch(ToggleEntity):
    """ Represents a Razberry Switch """

    def __init__(self, razberry_device, extra_data=None):
        self.razberry_device = razberry_device
        self.extra_data = extra_data
        if self.extra_data.get(int(self.razberry_device.instanceId)) and self.extra_data.get(int(self.razberry_device.instanceId)).get('name') :
            self._name = self.extra_data.get(int(self.razberry_device.instanceId)).get('name')
        else:
            if self.extra_data and self.extra_data.get('name'):
                self._name = self.extra_data.get('name')
            else:
                self._name = self.razberry_device.name
        
        self.is_on_status = False
        # for debouncing status check after command is sent
        self.last_command_send = 0

    @property
    def name(self):
        """ Get the name of the switch. """
        return self._name

    @property
    def state_attributes(self):
        attr = super().state_attributes

        attr['Razberry Device Id'] = self.razberry_device.razberry_device_id

        return attr

    def turn_on(self, **kwargs):
        self.last_command_send = time.time()
        self.razberry_device.switch_on()
        self.is_on_status = True

    def turn_off(self, **kwargs):
        self.last_command_send = time.time()
        self.razberry_device.switch_off()
        self.is_on_status = False

    @property
    def is_on(self):
        """ True if device is on. """
        return self.is_on_status

    def update(self):
        # We need to debounce the status call after turning switch on or off
        # because the razberry has some lag in updating the device status
        if (self.last_command_send + 3) < time.time():
            self.is_on_status = self.razberry_device.is_switched_on()
