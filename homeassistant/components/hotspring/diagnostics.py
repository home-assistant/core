"""Diagnostics support for Hot Spring."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import HotSpringConfigEntry

TO_REDACT = {"hostname", "mac_address", "ssid", "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HotSpringConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(asdict(entry.runtime_data.data.info), TO_REDACT)
