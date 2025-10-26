"""Diagnostics support for Blink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import BlinkConfigEntry

TO_REDACT = {"serial", "macaddress", "username", "password", "token", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: BlinkConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    api = config_entry.runtime_data.api

    data = {
        camera.name: dict(camera.attributes.items())
        for _, camera in api.cameras.items()
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "cameras": async_redact_data(data, TO_REDACT),
    }
