"""The Nord Pool component."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.util import dt as dt_util

from .const import DOMAIN, PLATFORMS
from .coordinator import NordPoolDataUpdateCoordinator

type NordPoolConfigEntry = ConfigEntry[NordPoolDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NordPoolConfigEntry) -> bool:
    """Set up Nord Pool from a config entry."""

    coordinator = NordPoolDataUpdateCoordinator(hass, entry)
    await coordinator.fetch_data(dt_util.utcnow())
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="initial_update_failed",
            translation_placeholders={"error": str(coordinator.last_exception)},
        )
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NordPoolConfigEntry) -> bool:
    """Unload Nord Pool config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
