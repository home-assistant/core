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
        VerisureThermometer(value)
        for value in verisure.get_climate_status().values()
        if verisure.SHOW_THERMOMETERS and
        hasattr(value, 'temperature') and value.temperature
        ])

    sensors.extend([
        VerisureHygrometer(value)
        for value in verisure.get_climate_status().values()
        if verisure.SHOW_HYGROMETERS and
        hasattr(value, 'humidity') and value.humidity
        ])

    add_devices(sensors)


class VerisureThermometer(Entity):
    """ represents a Verisure thermometer within home assistant. """

    def __init__(self, climate_status):
        self._id = climate_status.id
        self._device = verisure.MY_PAGES.DEVICE_CLIMATE

    @property
    def name(self):
        """ Returns the name of the device. """
        return '{} {}'.format(
            verisure.STATUS[self._device][self._id].location,
            "Temperature")

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
        ''' update sensor '''
        verisure.update()


class VerisureHygrometer(Entity):
    """ represents a Verisure hygrometer within home assistant. """

    def __init__(self, climate_status):
        self._id = climate_status.id
        self._device = verisure.MY_PAGES.DEVICE_CLIMATE

    @property
    def name(self):
        """ Returns the name of the device. """
        return '{} {}'.format(
            verisure.STATUS[self._device][self._id].location,
            "Humidity")

    @property
    def state(self):
        """ Returns the state of the device. """
        # remove % character
        return verisure.STATUS[self._device][self._id].humidity[:-1]

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity """
        return "%"

    def update(self):
        ''' update sensor '''
        verisure.update()
