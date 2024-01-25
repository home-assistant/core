"""Support for Lupusec Security System binary sensors."""
from __future__ import annotations

from datetime import timedelta
import logging

import lupupy.constants as CONST

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, LupusecDevice

SCAN_INTERVAL = timedelta(seconds=2)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_devices: AddEntitiesCallback,
) -> None:
    """Set up a binary sensors for a Lupusec device."""

    data = hass.data[DOMAIN][config_entry.entry_id]

    device_types = CONST.TYPE_OPENING + CONST.TYPE_SENSOR

    sensors = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        sensors.append(LupusecBinarySensor(data, device))

    async_add_devices(sensors)


class LupusecBinarySensor(LupusecDevice, BinarySensorEntity):
    """A binary sensor implementation for Lupusec device."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        if self._device.generic_type not in (
            item.value for item in BinarySensorDeviceClass
        ):
            return None
        return self._device.generic_type
