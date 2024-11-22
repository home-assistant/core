"""Diagnostics support for BraviaTV."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from . import BraviaTVConfigEntry

TO_REDACT = {CONF_MAC, CONF_PIN, "macAddr"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: BraviaTVConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    device_info = await coordinator.client.get_system_info()

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "device_info": async_redact_data(device_info, TO_REDACT),
    }
