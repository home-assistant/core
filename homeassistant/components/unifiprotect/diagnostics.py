"""Diagnostics support for UniFi Network."""

from __future__ import annotations

from typing import Any, cast

from uiprotect.test_util.anonymize import anonymize_data

from homeassistant.core import HomeAssistant

from .data import UFPConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: UFPConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    data = config_entry.runtime_data
    bootstrap = cast(dict[str, Any], anonymize_data(data.api.bootstrap.unifi_dict()))
    return {"bootstrap": bootstrap, "options": dict(config_entry.options)}
