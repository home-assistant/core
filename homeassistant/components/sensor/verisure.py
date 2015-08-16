"""
homeassistant.components.sensor.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Interfaces with Verisure sensors.
"""
import logging

import homeassistant.components.verisure as verisure

from homeassistant.helpers.entity import Entity
from homeassistant.const import TEMP_CELCIUS

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    sensors = []

    sensors.extend([
        VerisureClimateDevice(value)
        for value in verisure.get_climate_status().values()
        ])

    sensors.extend([
        VerisureAlarmDevice(value)
        for value in verisure.get_alarm_status().values()
        ])

    add_devices(sensors)


class VerisureClimateDevice(Entity):
    """ represents a Verisure climate sensor within home assistant. """

    def __init__(self, climate_status):
        self._id = climate_status.id
        self._device = verisure.MY_PAGES.DEVICE_CLIMATE

    @property
    def name(self):
        """ Returns the name of the device. """
        return verisure.STATUS[self._device][self._id].location

    @property
    def state(self):
        """ Returns the state of the device. """
        # remove ° character
        return verisure.STATUS[self._device][self._id].temperature[:-1]

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity """
        return TEMP_CELCIUS  # can verisure report in fahrenheit?

    def update(self):
        verisure.update()


class VerisureAlarmDevice(Entity):
    """ represents a Verisure alarm status within home assistant. """

    def __init__(self, alarm_status):
        self._id = alarm_status.id
        self._device = verisure.MY_PAGES.DEVICE_ALARM

    @property
    def name(self):
        """ Returns the name of the device. """
        return 'Alarm {}'.format(self._id)

    @property
    def state(self):
        """ Returns the state of the device. """
        return verisure.STATUS[self._device][self._id].label

    def update(self):
        verisure.update()
