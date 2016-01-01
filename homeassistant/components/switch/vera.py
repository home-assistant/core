"""
homeassistant.components.switch.vera
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Vera switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.vera/
"""
import logging
import time
from requests.exceptions import RequestException
import homeassistant.util.dt as dt_util

from homeassistant.helpers.entity import ToggleEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL, ATTR_TRIPPED, ATTR_ARMED, ATTR_LAST_TRIP_TIME)

REQUIREMENTS = ['https://github.com/pavoni/home-assistant-vera-api/archive/'
                'efdba4e63d58a30bc9b36d9e01e69858af9130b8.zip'
                '#python-vera==0.1.1']

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
        try:
            if (self.last_command_send + 5) < time.time():
                self.is_on_status = self.vera_device.is_switched_on()
        except RequestException:
            _LOGGER.warning('Could not update status for %s', self.name)
