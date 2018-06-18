"""
Support for temperature sensors in a GreenEye Monitor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensors.greeneye_monitor_temperature/
"""
import logging

from homeassistant.const import CONF_NAME, CONF_TEMPERATURE_UNIT
from homeassistant.helpers.entity import Entity

from ..greeneye_monitor import (
    CONF_MONITOR_SERIAL_NUMBER,
    CONF_NUMBER,
    DATA_GREENEYE_MONITOR,
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['greeneye_monitor']

TEMPERATURE_ICON = 'mdi:thermometer'


async def async_setup_platform(
        hass,
        config,
        async_add_devices,
        discovery_info=None):
    """Set up a single GEM temperature sensor."""
    async_add_devices([
        TemperatureSensor(
            discovery_info[CONF_MONITOR_SERIAL_NUMBER],
            discovery_info[CONF_NUMBER],
            discovery_info[CONF_NAME],
            discovery_info[CONF_TEMPERATURE_UNIT])])


class TemperatureSensor(Entity):
    """Entity showing temperature from one temperature sensor."""

    should_poll = False

    def __init__(self, monitor_serial_number, number, name, unit):
        """Construct the entity."""
        self._monitor_serial_number = monitor_serial_number
        self._number = number
        self._sensor = None
        self._name = name
        self._unit = unit

    async def async_added_to_hass(self):
        """Wait for and connect to the temperature sensor."""
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]

        if not self._try_connect_to_monitor(monitors):
            monitors.add_listener(self._on_new_monitor)

    def _on_new_monitor(self, *args):
        monitors = self.hass.data[DATA_GREENEYE_MONITOR]
        if self._try_connect_to_monitor(monitors):
            monitors.remove_listener(self._on_new_monitor)

    async def async_will_remove_from_hass(self):
        """Remove listener from the sensor."""
        if self._sensor:
            self._sensor.remove_listener(self._schedule_update)
        else:
            monitors = self.hass.data[DATA_GREENEYE_MONITOR]
            monitors.remove_listener(self._on_new_monitor)

    def _try_connect_to_monitor(self, monitors):
        monitor = monitors.monitors.get(self._monitor_serial_number, None)
        if not monitor:
            return False

        self._sensor = monitor.temperature_sensors[self._number - 1]
        self._sensor.add_listener(self._schedule_update)

        return True

    def _schedule_update(self):
        self.async_schedule_update_ha_state(False)

    @property
    def unique_id(self):
        """Return a unique identifier for this temperature sensor."""
        return "{serial}-{number}".format(
            serial=self._monitor_serial_number,
            number=self._number)

    @property
    def name(self):
        """Return the name of the temperature sensor."""
        return self._name

    @property
    def state(self):
        """Return the current temperature being reported by this sensor."""
        if not self._sensor:
            return None

        return self._sensor.temperature

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement for this sensor (user specified)."""
        return self._unit

    @property
    def icon(self):
        """Return the icon to use for this entity."""
        return TEMPERATURE_ICON
