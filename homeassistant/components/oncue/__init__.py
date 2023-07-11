"""The Oncue integration."""
from __future__ import annotations

from datetime import timedelta
import logging

from aiooncue import LoginFailedException, Oncue

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONNECTION_EXCEPTIONS, DOMAIN

PLATFORMS: list[str] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oncue from a config entry."""
    data = entry.data
    websession = async_get_clientsession(hass)
    client = Oncue(data[CONF_USERNAME], data[CONF_PASSWORD], websession)
    try:
        await client.async_login()
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady(ex) from ex
    except LoginFailedException as ex:
        _LOGGER.error("Failed to login to oncue service: %s", ex)
        return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Oncue {entry.data[CONF_USERNAME]}",
        update_interval=timedelta(minutes=10),
        update_method=client.async_fetch_all,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
