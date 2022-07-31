"""Diagnostics support for Kostal Plenticore."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .helper import Plenticore

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, dict[str, Any]]:
    """Return diagnostics for a config entry."""
    data = {"config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT)}

    plenticore: Plenticore = hass.data[DOMAIN][config_entry.entry_id]

    # Get information from Kostal Plenticore library
    available_process_data = await plenticore.client.get_process_data()
    available_settings_data = await plenticore.client.get_settings()
    data["client"] = {
        "version": str(await plenticore.client.get_version()),
        "me": str(await plenticore.client.get_me()),
        "available_process_data": available_process_data,
        "available_settings_data": {
            module_id: [str(setting) for setting in settings]
            for module_id, settings in available_settings_data.items()
        },
    }

    device_info = {**plenticore.device_info}
    device_info["identifiers"] = REDACTED  # contains serial number
    data["device"] = device_info

    return data
