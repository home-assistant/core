"""Integration to integrate TuneBlade Remote devices with Home Assistant."""

import logging

from pytuneblade import TuneBladeApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN
from .coordinator import TuneBladeDataUpdateCoordinator
from .types import TuneBladeRuntimeData

_LOGGER = logging.getLogger(__name__)


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

    await coordinator.async_init()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.runtime_data = TuneBladeRuntimeData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, ["media_player"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload TuneBlade config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, ["media_player"]
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
