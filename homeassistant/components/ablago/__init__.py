"""The Ablago integration: counters of one person in a self-hosted Ablago."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import (
    AblagoConfigEntry,
    AblagoCounterCoordinator,
    AblagoData,
    AblagoHealthCoordinator,
    create_client,
)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AblagoConfigEntry) -> None:
    """Set up Ablago from a config entry."""
    client = create_client(hass, dict(entry.data))

    counters = AblagoCounterCoordinator(hass, entry, client)
    health = AblagoHealthCoordinator(hass, entry, client)

    await counters.async_config_entry_first_refresh()
    await health.async_config_entry_first_refresh()

    entry.runtime_data = AblagoData(counters=counters, health=health)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AblagoConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
