"""Diagnostics support for UniFi Network."""

from __future__ import annotations

from typing import Any, cast

from pyunifiprotect.test_util.anonymize import anonymize_data

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .data import ProtectData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data: ProtectData = hass.data[DOMAIN][config_entry.entry_id]
    bootstrap = cast(dict[str, Any], anonymize_data(data.api.bootstrap.unifi_dict()))
    return {"bootstrap": bootstrap, "options": dict(config_entry.options)}
