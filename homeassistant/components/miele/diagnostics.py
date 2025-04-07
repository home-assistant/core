"""Diagnostics support for Miele."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import MieleConfigEntry

TO_REDACT = {"access_token", "refresh_token", "serialNumber"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: MieleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    miele_data = {}
    devices = {
        device_id: device_data.raw
        for device_id, device_data in config_entry.runtime_data.data.devices.items()
    }
    actions = {
        device_id: action_data.raw
        for device_id, action_data in config_entry.runtime_data.data.actions.items()
    }
    miele_data["devices"] = devices
    miele_data["actions"] = actions

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "miele_data": async_redact_data(miele_data, TO_REDACT),
    }
