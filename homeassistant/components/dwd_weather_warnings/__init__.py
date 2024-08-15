"""The dwd_weather_warnings component."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, PLATFORMS
from .coordinator import DwdWeatherWarningsConfigEntry, DwdWeatherWarningsCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: DwdWeatherWarningsConfigEntry
) -> bool:
    """Set up a config entry."""
    device_registry = dr.async_get(hass)
    if device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)}):
        device_registry.async_clear_config_entry(entry.entry_id)
    coordinator = DwdWeatherWarningsCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: DwdWeatherWarningsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
