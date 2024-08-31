"""Fetches diagnostic data for Starlink systems."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import StarlinkUpdateCoordinator

TO_REDACT = {"id", "latitude", "longitude", "altitude"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Starlink config entries."""
    coordinator: StarlinkUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(asdict(coordinator.data), TO_REDACT)
