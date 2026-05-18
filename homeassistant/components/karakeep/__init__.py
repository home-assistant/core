"""The Karakeep integration."""

from aiokarakeep import KarakeepClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import KarakeepDataUpdateCoordinator

type KarakeepConfigEntry = ConfigEntry[KarakeepDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: KarakeepConfigEntry) -> bool:
    """Set up Karakeep from a config entry."""
    client = KarakeepClient(
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        async_get_clientsession(hass),
    )
    coordinator = KarakeepDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KarakeepConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
