"""The JustNimbus integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import PLATFORMS
from .coordinator import JustNimbusConfigEntry, JustNimbusCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: JustNimbusConfigEntry) -> bool:
    """Set up JustNimbus from a config entry."""
    if "zip_code" in entry.data:
        coordinator = JustNimbusCoordinator(hass, entry)
    else:
        raise ConfigEntryAuthFailed
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: JustNimbusConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
