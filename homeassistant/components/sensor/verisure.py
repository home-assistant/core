"""
Interfaces with Verisure sensors.

For more details about this platform, please refer to the documentation at
documentation at https://home-assistant.io/components/verisure/
"""
import logging

import homeassistant.components.verisure as verisure
from homeassistant.const import TEMP_CELCIUS
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Sets up the Verisure platform."""
    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    sensors = []

    sensors.extend([
        VerisureThermometer(value)
        for value in verisure.CLIMATE_STATUS.values()
        if verisure.SHOW_THERMOMETERS and
        hasattr(value, 'temperature') and value.temperature
        ])

    sensors.extend([
        VerisureHygrometer(value)
        for value in verisure.CLIMATE_STATUS.values()
        if verisure.SHOW_HYGROMETERS and
        hasattr(value, 'humidity') and value.humidity
        ])

    sensors.extend([
        VerisureMouseDetection(value)
        for value in verisure.MOUSEDETECTION_STATUS.values()
        if verisure.SHOW_MOUSEDETECTION and
        hasattr(value, 'amountText') and value.amountText
        ])

    add_devices(sensors)


class VerisureThermometer(Entity):
    """Represents a Verisure thermometer."""

    def __init__(self, climate_status):
        self._id = climate_status.id

    @property
    def name(self):
        """Returns the name of the device."""
        return '{} {}'.format(
            verisure.CLIMATE_STATUS[self._id].location,
            "Temperature")

    @property
    def state(self):
        """Returns the state of the device."""
        # remove ° character
        return verisure.CLIMATE_STATUS[self._id].temperature[:-1]

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this entity."""
        return TEMP_CELCIUS  # can verisure report in fahrenheit?

    def update(self):
        """Update the sensor."""
        verisure.update_climate()


class VerisureHygrometer(Entity):
    """Represents a Verisure hygrometer."""

    def __init__(self, climate_status):
        self._id = climate_status.id

    @property
    def name(self):
        """Returns the name of the sensor."""
        return '{} {}'.format(
            verisure.CLIMATE_STATUS[self._id].location,
            "Humidity")

    @property
    def state(self):
        """Returns the state of the sensor."""
        # remove % character
        return verisure.CLIMATE_STATUS[self._id].humidity[:-1]

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this sensor."""
        return "%"

    def update(self):
        """Update sensor the sensor."""
        verisure.update_climate()


class VerisureMouseDetection(Entity):
    """ Represents a Verisure mouse detector."""

    def __init__(self, mousedetection_status):
        self._id = mousedetection_status.deviceLabel

    @property
    def name(self):
        """Returns the name of the sensor."""
        return '{} {}'.format(
            verisure.MOUSEDETECTION_STATUS[self._id].location,
            "Mouse")

    @property
    def state(self):
        """Returns the state of the sensor."""
        return verisure.MOUSEDETECTION_STATUS[self._id].count

    @property
    def unit_of_measurement(self):
        """Unit of measurement of this sensor."""
        return "Mice"

    def update(self):
        """Update the sensor."""
        verisure.update_mousedetection()
