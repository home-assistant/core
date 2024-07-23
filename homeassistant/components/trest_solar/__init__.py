"""The TrestSolarController integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TrestDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


@dataclass
class RuntimeData:
    """Runtime data class."""

    coordinator: TrestDataCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TrestSolarController from a config entry."""
    coordinator = TrestDataCoordinator(hass, _LOGGER)
    await coordinator.async_config_entry_first_refresh()

    # Use hass.data to store runtime data
    if "runtime_data" not in hass.data:
        hass.data["runtime_data"] = {}
    hass.data["runtime_data"][entry.entry_id] = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
