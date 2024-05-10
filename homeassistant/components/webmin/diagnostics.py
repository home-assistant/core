"""Diagnostics support for Webmin."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WebminUpdateCoordinator

TO_REDACT = {
    CONF_HOST,
    CONF_UNIQUE_ID,
    CONF_USERNAME,
    CONF_PASSWORD,
    "address",
    "address6",
    "ether",
    "broadcast",
    "device",
    "dir",
    "title",
    "entry_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: WebminUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(
        {"entry": entry.as_dict(), "data": coordinator.data}, TO_REDACT
    )
