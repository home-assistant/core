"""Manages a connection to the Nanoleaf API."""

from typing import cast

from aionanoleaf import Nanoleaf

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import NanoleafEntryData
from .const import DOMAIN


def get_entry_data(hass: HomeAssistant, config_entry: str) -> NanoleafEntryData:
    """Get (type-safe) Nanoleaf entry data given a config entry ID."""
    return cast(NanoleafEntryData, hass.data[DOMAIN][config_entry])


def get_nanoleaf_connection_by_device_id(
    hass: HomeAssistant, device_id: str
) -> Nanoleaf | None:
    """Get a Nanoleaf device connection for the given device id."""
    device_registry = dr.async_get(hass)
    if device := device_registry.async_get(device_id):
        for config_entry in device.config_entries:
            if not (entry_data := get_entry_data(hass, config_entry)):
                continue

            if connection := entry_data.device:
                return connection

    return None
