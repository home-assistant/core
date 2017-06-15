"""
Interfaces with Verisure sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.verisure/
"""
import logging

from homeassistant.components.verisure import HUB as hub
from homeassistant.components.verisure import (
    CONF_THERMOMETERS, CONF_HYDROMETERS, CONF_MOUSE)
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Verisure platform."""
    sensors = []

    if int(hub.config.get(CONF_THERMOMETERS, 1)):
        hub.update_climate()
        sensors.extend([
            VerisureThermometer(value.id)
            for value in hub.climate_status.values()
            if hasattr(value, 'temperature') and value.temperature
            ])

    if int(hub.config.get(CONF_HYDROMETERS, 1)):
        hub.update_climate()
        sensors.extend([
            VerisureHygrometer(value.id)
            for value in hub.climate_status.values()
            if hasattr(value, 'humidity') and value.humidity
            ])

    if int(hub.config.get(CONF_MOUSE, 1)):
        hub.update_mousedetection()
        sensors.extend([
            VerisureMouseDetection(value.deviceLabel)
            for value in hub.mouse_status.values()
            # is this if needed?
            if hasattr(value, 'amountText') and value.amountText
            ])

    add_devices(sensors)


class VerisureThermometer(Entity):
    """Representation of a Verisure thermometer."""

    def __init__(self, device_id):
        """Initialize the sensor."""
        self._id = device_id

    @property
    def name(self):
        """Return the name of the device."""
        return '{} {}'.format(
            hub.climate_status[self._id].location, 'Temperature')

    @property
    def state(self):
        """Return the state of the device."""
        # Remove ° character
        return hub.climate_status[self._id].temperature[:-1]

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS

    def update(self):
        """Update the sensor."""
        hub.update_climate()


class VerisureHygrometer(Entity):
    """Representation of a Verisure hygrometer."""

    def __init__(self, device_id):
        """Initialize the sensor."""
        self._id = device_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(
            hub.climate_status[self._id].location, 'Humidity')

    @property
    def state(self):
        """Return the state of the sensor."""
        # remove % character
        return hub.climate_status[self._id].humidity[:-1]

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return "%"

    def update(self):
        """Update the sensor."""
        hub.update_climate()


class VerisureMouseDetection(Entity):
    """Representation of a Verisure mouse detector."""

    def __init__(self, device_id):
        """Initialize the sensor."""
        self._id = device_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(
            hub.mouse_status[self._id].location, 'Mouse')

    @property
    def state(self):
        """Return the state of the sensor."""
        return hub.mouse_status[self._id].count

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.available

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this sensor."""
        return "Mice"

    def update(self):
        """Update the sensor."""
        hub.update_mousedetection()
