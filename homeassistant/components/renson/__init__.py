"""The Renson integration."""
from __future__ import annotations

from dataclasses import dataclass

from renson_endura_delta.renson import RensonVentilation

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import RensonCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.FAN,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.TIME,
]


@dataclass
class RensonData:
    """Renson data class."""

    api: RensonVentilation
    coordinator: RensonCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Renson from a config entry."""

    api = RensonVentilation(entry.data[CONF_HOST])
    coordinator = RensonCoordinator("Renson", hass, api)

    if not await hass.async_add_executor_job(api.connect):
        raise ConfigEntryNotReady("Cannot connect to Renson device")

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = RensonData(
        api,
        coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
