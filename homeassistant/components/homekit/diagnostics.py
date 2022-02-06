"""Diagnostics support for HomeKit."""
from __future__ import annotations

from typing import Any

from pyhap.accessory_driver import AccessoryDriver
from pyhap.state import State

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import HomeKit
from .const import DOMAIN, HOMEKIT


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    homekit: HomeKit = hass.data[DOMAIN][entry.entry_id][HOMEKIT]
    driver: AccessoryDriver = homekit.driver
    state: State = driver.state
    return {
        "config-entry": {
            "title": entry.title,
            "version": entry.version,
            "data": entry.data,
        },
        "accessories": homekit.driver.get_accessories(),
        "paired_clients": state.paired_clients,
        "client_properties": state.client_properties,
        "config_version": state.config_version,
        "pairing_id": state.mac,
    }
