"""
homeassistant.components.switch.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera switches.

Configuration:
To use the Vera lights you will need to add something like the following to
your configuration.yaml file.

switch:
    platform: vera
    vera_controller_url: http://YOUR_VERA_IP:3480/
    device_data:
        12:
            name: My awesome switch
            exclude: true
        13:
            name: Another Switch

Variables:

vera_controller_url
*Required
This is the base URL of your vera controller including the port number if not
running on 80. Example: http://192.168.1.21:3480/

device_data
*Optional
This contains an array additional device info for your Vera devices.  It is not
required and if not specified all lights configured in your Vera controller
will be added with default values.  You should use the id of your vera device
as the key for the device within device_data.

These are the variables for the device_data array:

name
*Optional
This parameter allows you to override the name of your Vera device in the HA
interface, if not specified the value configured for the device in your Vera
will be used.

exclude
*Optional
This parameter allows you to exclude the specified device from homeassistant,
it should be set to "true" if you want this device excluded.
"""
import logging
import time
from requests.exceptions import RequestException
import homeassistant.util.dt as dt_util

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TRIPPED, ATTR_ARMED, ATTR_LAST_TRIP_TIME)

REQUIREMENTS = ['https://github.com/balloob/home-assistant-vera-api/archive/'
                'a8f823066ead6c7da6fb5e7abaf16fef62e63364.zip'
                '#python-vera==0.1']

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Vera switches. """
    import pyvera as veraApi

    base_url = config.get('vera_controller_url')
    if not base_url:
        _LOGGER.error(
            "The required parameter 'vera_controller_url'"
            " was not found in config"
        )
        return False

    device_data = config.get('device_data', {})

    vera_controller = veraApi.VeraController(base_url)
    devices = []
    try:
        devices = vera_controller.get_devices([
            'Switch', 'Armable Sensor', 'On/Off Switch'])
    except RequestException:
        # There was a network related error connecting to the vera controller.
        _LOGGER.exception("Error communicating with Vera API")
        return False

    vera_switches = []
    for device in devices:
        extra_data = device_data.get(device.deviceId, {})
        exclude = extra_data.get('exclude', False)

        if exclude is not True:
            vera_switches.append(VeraSwitch(device, extra_data))

    return vera_switches


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Vera lights. """
    add_devices(get_devices(hass, config))


class VeraSwitch(ToggleEntity):
    """ Represents a Vera Switch. """

    def __init__(self, vera_device, extra_data=None):
        self.vera_device = vera_device
        self.extra_data = extra_data
        if self.extra_data and self.extra_data.get('name'):
            self._name = self.extra_data.get('name')
        else:
            self._name = self.vera_device.name
        self.is_on_status = False
        # for debouncing status check after command is sent
        self.last_command_send = 0

    @property
    def name(self):
        """ Get the mame of the switch. """
        return self._name

    @property
    def state_attributes(self):
        attr = super().state_attributes or {}

        if self.vera_device.has_battery:
            attr[ATTR_BATTERY_LEVEL] = self.vera_device.battery_level + '%'

        if self.vera_device.is_armable:
            armed = self.vera_device.refresh_value('Armed')
            attr[ATTR_ARMED] = 'True' if armed == '1' else 'False'

        if self.vera_device.is_trippable:
            last_tripped = self.vera_device.refresh_value('LastTrip')
            if last_tripped is not None:
                utc_time = dt_util.utc_from_timestamp(int(last_tripped))
                attr[ATTR_LAST_TRIP_TIME] = dt_util.datetime_to_str(
                    utc_time)
            else:
                attr[ATTR_LAST_TRIP_TIME] = None
            tripped = self.vera_device.refresh_value('Tripped')
            attr[ATTR_TRIPPED] = 'True' if tripped == '1' else 'False'

        attr['Vera Device Id'] = self.vera_device.vera_device_id

        return attr

    def turn_on(self, **kwargs):
        self.last_command_send = time.time()
        self.vera_device.switch_on()
        self.is_on_status = True

    def turn_off(self, **kwargs):
        self.last_command_send = time.time()
        self.vera_device.switch_off()
        self.is_on_status = False

    @property
    def is_on(self):
        """ True if device is on. """
        return self.is_on_status

    def update(self):
        # We need to debounce the status call after turning switch on or off
        # because the vera has some lag in updating the device status
        if (self.last_command_send + 5) < time.time():
            self.is_on_status = self.vera_device.is_switched_on()
