"""The Oncue integration."""

from __future__ import annotations

import logging

from aiokem.exceptions import AuthenticationCredentialsError
from aiokem.main import AioKem

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONNECTION_EXCEPTIONS
from .coordinator import KemUpdateCoordinator

PLATFORMS: list[str] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oncue from a config entry."""
    data = entry.data
    websession = async_get_clientsession(hass)
    kem = AioKem(session=websession)
    try:
        await kem.authenticate(data[CONF_USERNAME], data[CONF_PASSWORD])
    except AuthenticationCredentialsError as ex:
        raise ConfigEntryAuthFailed from ex
    except CONNECTION_EXCEPTIONS as ex:
        raise ConfigEntryNotReady from ex

    coordinator = KemUpdateCoordinator(
        hass=hass,
        logger=_LOGGER,
        config_entry=entry,
        kem=kem,
        name="kem",  # needs to be unique per entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
