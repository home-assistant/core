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
    data: dict[str, Any] = {
        "status": homekit.status,
        "config-entry": {
            "title": entry.title,
            "version": entry.version,
            "data": dict(entry.data),
            "options": dict(entry.options),
        },
    }
    if not hasattr(homekit, "driver"):
        return data
    driver: AccessoryDriver = homekit.driver
    data.update(driver.get_accessories())
    state: State = driver.state
    data.update(
        {
            "client_properties": {
                str(client): props for client, props in state.client_properties.items()
            },
            "config_version": state.config_version,
            "pairing_id": state.mac,
        }
    )
    return data
