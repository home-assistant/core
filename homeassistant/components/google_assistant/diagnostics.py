"""Diagnostics support for Hue."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.components.diagnostics.const import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .http import GoogleConfig
from .smart_home import async_devices_serialize

TO_REDACT = [
    "uuid",
    "baseUrl",
    "webhookId",
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostic information."""
    config: GoogleConfig = hass.data[DOMAIN][entry.entry_id]

    devices = await async_devices_serialize(hass, config, REDACTED)

    return {"sync": async_redact_data(devices, TO_REDACT)}
