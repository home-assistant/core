"""Diagnostics support for the VelaSmart integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import VelasmartConfigEntry

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "gateway_mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: VelasmartConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator
    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "devices": async_redact_data(coordinator.data, TO_REDACT),
    }
