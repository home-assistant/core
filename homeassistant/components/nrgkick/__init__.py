"""The NRGkick integration."""

from __future__ import annotations

from nrgkick_api import NRGkickAPI

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import NRGkickConfigEntry, NRGkickDataUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: NRGkickConfigEntry) -> bool:
    """Set up NRGkick from a config entry."""
    api = NRGkickAPI(
        host=entry.data[CONF_HOST],
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        session=async_get_clientsession(hass),
    )

    coordinator = NRGkickDataUpdateCoordinator(hass, api, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NRGkickConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
