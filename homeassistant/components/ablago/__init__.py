"""The Ablago integration: counters of one person in a self-hosted Ablago."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AblagoConfigEntry, AblagoCounterCoordinator, create_client

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AblagoConfigEntry) -> None:
    """Set up Ablago from a config entry."""
    coordinator = AblagoCounterCoordinator(
        hass, entry, create_client(hass, dict(entry.data))
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AblagoConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
