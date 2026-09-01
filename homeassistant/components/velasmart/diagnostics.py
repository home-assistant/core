"""Diagnostics support for the VelaSmart integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {CONF_PASSWORD, CONF_USERNAME, "gateway_mac"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    return {
        "config_entry": async_redact_data(entry.data, TO_REDACT),
        "devices": async_redact_data(coordinator.data, TO_REDACT),
    }
