"""
A sensor platform which detects underruns and capped status from the official Raspberry Pi Kernel.

Minimal Kernel needed is 4.14+
"""
import logging

from rpi_bad_power import new_under_voltage

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_NORMALIZED = "Voltage normalized. Everything is working as intended."
DESCRIPTION_UNDER_VOLTAGE = "Under-voltage was detected. Consider getting a uninterruptible power supply for your Raspberry Pi."


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities
):
    """Set up rpi_power binary sensor."""
    under_voltage = await hass.async_add_executor_job(new_under_voltage)
    async_add_entities([RaspberryChargerBinarySensor(under_voltage)], True)


class RaspberryChargerBinarySensor(BinarySensorEntity):
    """Binary sensor representing the rpi power status."""

    def __init__(self, under_voltage):
        """Initialize the binary sensor."""
        self._under_voltage = under_voltage
        self._is_on = None
        self._last_is_on = False

    def update(self):
        """Update the state."""
        self._is_on = self._under_voltage.get()
        if self._is_on != self._last_is_on:
            if self._is_on:
                _LOGGER.warning(DESCRIPTION_UNDER_VOLTAGE)
            else:
                _LOGGER.info(DESCRIPTION_NORMALIZED)
            self._last_is_on = self._is_on

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return "rpi_power"  # only one sensor possible

    @property
    def name(self):
        """Return the name of the sensor."""
        return "RPi Power status"

    @property
    def is_on(self):
        """Return if there is a problem detected."""
        return self._is_on

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:raspberry-pi"

    @property
    def device_class(self):
        """Return the class of this device."""
        return DEVICE_CLASS_PROBLEM
