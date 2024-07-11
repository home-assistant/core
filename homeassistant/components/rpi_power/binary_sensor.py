"""A sensor platform which detects underruns and capped status from the official Raspberry Pi Kernel.

Minimal Kernel needed is 4.14+
"""

import logging

from rpi_bad_power import UnderVoltage, new_under_voltage

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)

DESCRIPTION_NORMALIZED = "Voltage normalized. Everything is working as intended."
DESCRIPTION_UNDER_VOLTAGE = (
    "Under-voltage was detected. Consider getting a uninterruptible power supply for"
    " your Raspberry Pi."
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up rpi_power binary sensor."""
    under_voltage = await hass.async_add_executor_job(new_under_voltage)
    async_add_entities([RaspberryChargerBinarySensor(under_voltage)], True)


class RaspberryChargerBinarySensor(BinarySensorEntity):
    """Binary sensor representing the rpi power status."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:raspberry-pi"
    _attr_name = "RPi Power status"
    _attr_unique_id = "rpi_power"  # only one sensor possible

    def __init__(self, under_voltage: UnderVoltage) -> None:
        """Initialize the binary sensor."""
        self._under_voltage = under_voltage

    def update(self) -> None:
        """Update the state."""
        value = self._under_voltage.get()
        if self._attr_is_on != value:
            if value:
                _LOGGER.warning(DESCRIPTION_UNDER_VOLTAGE)
            else:
                _LOGGER.info(DESCRIPTION_NORMALIZED)
            self._attr_is_on = value
