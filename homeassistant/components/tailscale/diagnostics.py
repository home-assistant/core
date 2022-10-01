"""Diagnostics support for Tailscale."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_TAILNET, DOMAIN
from .coordinator import TailscaleDataUpdateCoordinator

TO_REDACT = {
    CONF_API_KEY,
    CONF_TAILNET,
    "addresses",
    "device_id",
    "endpoints",
    "hostname",
    "machine_key",
    "name",
    "node_key",
    "user",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TailscaleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Round-trip via JSON to trigger serialization
    devices = [json.loads(device.json()) for device in coordinator.data.values()]
    return async_redact_data({"devices": devices}, TO_REDACT)
