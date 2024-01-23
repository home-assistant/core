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

    device_types = CONST.TYPE_SWITCH

    devices = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        devices.append(LupusecSwitch(data, device))

    add_entities(devices)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Set up Lupusec switch devices."""
    data = hass.data[LUPUSEC_DOMAIN]

    device_types = CONST.TYPE_SWITCH

    switches = []
    for device in data.lupusec.get_devices(generic_type=device_types):
        switches.append(LupusecSwitch(data, device, config_entry))

    async_add_devices(switches)


def get_unique_id(config_entry_id: str, key: str) -> str:
    """Create a unique_id id for a lupusec entity."""
    return f"{LUPUSEC_DOMAIN}_{config_entry_id}_{key}"


class LupusecSwitch(LupusecDevice, SwitchEntity):
    """Representation of a Lupusec switch."""

    def __init__(self, data, device, config_entry=None) -> None:
        """Initialize a LupusecSwitch."""
        super().__init__(data, device, config_entry)
        self._attr_unique_id = get_unique_id(config_entry.entry_id, device.device_id)

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
