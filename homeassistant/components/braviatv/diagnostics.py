"""Diagnostics support for BraviaTV."""
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_PIN
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import BraviaTVCoordinator

TO_REDACT = {CONF_MAC, CONF_PIN, "macAddr"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: BraviaTVCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    device_info = await coordinator.client.get_system_info()

    diagnostics_data = {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "device_info": async_redact_data(device_info, TO_REDACT),
    }

    return diagnostics_data
