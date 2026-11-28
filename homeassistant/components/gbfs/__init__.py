"""The General Bikeshare Feed Specification (GBFS) integration."""

from aiomobilitydatabase.feeds import MobilityFeedsClient, MobilityFeedsError

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import GbfsConfigEntry, GbfsCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: GbfsConfigEntry) -> None:
    """Set up a GBFS system from a config entry."""
    client = MobilityFeedsClient(session=async_get_clientsession(hass))
    try:
        feed = await client.get_gbfs_feed_from_url(entry.data[CONF_URL])
        system = await feed.get_system_info()
    except MobilityFeedsError as err:
        raise ConfigEntryNotReady(f"Error reading GBFS system: {err}") from err
    coordinator = GbfsCoordinator(hass, entry, feed, system)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: GbfsConfigEntry) -> None:
    """Reload when stations are added or removed."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GbfsConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
