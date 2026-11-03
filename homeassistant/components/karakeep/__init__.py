"""The Karakeep integration."""

from aiokarakeep import KarakeepClient

from homeassistant.const import CONF_TOKEN, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import KarakeepConfigEntry, KarakeepDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: KarakeepConfigEntry) -> None:
    """Set up Karakeep from a config entry."""
    client = KarakeepClient(
        entry.data[CONF_URL],
        entry.data[CONF_TOKEN],
        async_get_clientsession(hass, entry.data[CONF_VERIFY_SSL]),
    )
    coordinator = KarakeepDataUpdateCoordinator(hass, entry, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: KarakeepConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
