"""Diagnostics support for Nest."""

from __future__ import annotations

from typing import Any

from rtsp_to_webrtc import client

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return dict(client.get_diagnostics())
