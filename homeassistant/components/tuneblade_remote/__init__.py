"""Integration to integrate TuneBlade Remote devices with Home Assistant."""

import logging

from pytuneblade import TuneBladeApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import PLATFORMS
from .coordinator import TuneBladeDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type TuneBladeConfigEntry = ConfigEntry[TuneBladeDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: TuneBladeConfigEntry) -> bool:
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

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: TuneBladeConfigEntry) -> bool:
    """Unload TuneBlade config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data = None  # type: ignore[assignment]
    return unload_ok
