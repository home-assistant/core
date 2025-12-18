"""The NRGkick integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NRGkickAPI
from .coordinator import NRGkickConfigEntry, NRGkickDataUpdateCoordinator
from .entity import NRGkickEntity

# Re-export for backward compatibility with other modules.
__all__ = [
    "NRGkickConfigEntry",
    "NRGkickDataUpdateCoordinator",
    "NRGkickEntity",
]

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: NRGkickConfigEntry) -> bool:
    """Set up NRGkick from a config entry."""
    api = NRGkickAPI(
        host=entry.data["host"],
        username=entry.data.get("username"),
        password=entry.data.get("password"),
        session=async_get_clientsession(hass),
    )

    coordinator = NRGkickDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener for options changes.
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_reload_entry(hass: HomeAssistant, entry: NRGkickConfigEntry) -> None:
    """Reload the config entry when it changed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NRGkickConfigEntry) -> bool:
    """Unload a config entry."""
    result: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return result
