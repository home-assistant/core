import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.const import CONF_HOST, CONF_PORT

from .tuneblade import TuneBladeApiClient
from .coordinator import TuneBladeDataUpdateCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up TuneBlade integration from a config entry."""

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    session = async_create_clientsession(hass)

    client = TuneBladeApiClient(
        host=host,
        port=port,
        session=session,
    )

    coordinator = TuneBladeDataUpdateCoordinator(hass, client)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Error connecting to TuneBlade hub: %s", err)
        raise ConfigEntryNotReady from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, ["media_player", "switch"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TuneBlade config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["media_player", "switch"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
