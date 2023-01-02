"""Support for Lupusec Security System switches."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import lupupy.constants as CONST

from homeassistant.components.switch import SwitchEntity
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
    """Set up Lupusec switch devices."""
    if discovery_info is None:
        return

    data = hass.data[LUPUSEC_DOMAIN]

    devices = []

    for device in data.lupusec.get_devices(generic_type=CONST.TYPE_SWITCH):

        devices.append(LupusecSwitch(data, device))

    add_entities(devices)


class LupusecSwitch(LupusecDevice, SwitchEntity):
    """Representation of a Lupusec switch."""

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on
