"""Support for Lupusec Security System binary sensors."""
from __future__ import annotations

from datetime import timedelta

import lupupy.constants as CONST

from homeassistant.components.binary_sensor import DEVICE_CLASSES, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as LUPUSEC_DOMAIN, LupusecDevice

SCAN_INTERVAL = timedelta(seconds=2)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for an Lupusec device."""
    if discovery_info is None:
        return

    data = hass.data[LUPUSEC_DOMAIN]

    device_types = [CONST.TYPE_OPENING]

    devices = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        devices.append(LupusecBinarySensor(data, device))

    add_entities(devices)


class LupusecBinarySensor(LupusecDevice, BinarySensorEntity):
    """A binary sensor implementation for Lupusec device."""

    @property
    def is_on(self):
        """Return True if the binary sensor is on."""
        return self._device.is_on

    @property
    def device_class(self):
        """Return the class of the binary sensor."""
        if self._device.generic_type not in DEVICE_CLASSES:
            return None
        return self._device.generic_type
