"""Support for Lupusec Security System switches."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from typing import Any

import lupupy.constants as CONST

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DOMAIN
from .entity import LupusecBaseSensor

SCAN_INTERVAL = timedelta(seconds=2)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Lupusec switch devices."""

    data = hass.data[DOMAIN][config_entry.entry_id]

    device_types = CONST.TYPE_SWITCH

    partial_func = partial(data.get_devices, generic_type=device_types)
    devices = await hass.async_add_executor_job(partial_func)

    async_add_entities(
        LupusecSwitch(device, config_entry.entry_id) for device in devices
    )


class LupusecSwitch(LupusecBaseSensor, SwitchEntity):
    """Representation of a Lupusec switch."""

    _attr_name = None

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on the device."""
        self._device.switch_on()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the device."""
        self._device.switch_off()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.is_on
