"""Diagnostics support for Blink."""
from __future__ import annotations

from typing import Any

from blinkpy.blinkpy import Blink

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {"serial", "macaddress", "username", "password", "token", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api: Blink = hass.data[DOMAIN][config_entry.entry_id].api

    data = {
        camera.name: dict(camera.attributes.items())
        for _, camera in api.cameras.items()
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "cameras": async_redact_data(data, TO_REDACT),
    }
