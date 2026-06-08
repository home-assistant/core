"""The Theben Conexa Smartmeter gateway integration."""

import logging

import aiohttp

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import SmgwSensorCoordinator, ThebenConfigEntry, ThebenRuntimeData
from .smgw import ConexaSMGW, checkNetworkConnection

_LOGGER = logging.getLogger(__name__)

_PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> bool:
    """Set up Theben Conexa Smartmeter gateway from a config entry."""

    try:
        # This function tries to establish a TCP connection and raises an exception on error
        await checkNetworkConnection(entry.data[CONF_HOST])
    except (OSError, aiohttp.ClientError) as e:
        raise ConfigEntryNotReady("Device is not reachable") from e

    coordinator = SmgwSensorCoordinator(hass, entry)

    try:
        # Unfortunately the Conexa 3.0 doesn't provide separate authentication feedback it just ignores all requests with invalid username/password,
        # That's why here we need to assume it failed because of wrong credentials, as we checked for connectivity just before and the device was reachable.
        entry.runtime_data = ThebenRuntimeData(
            api=await ConexaSMGW.create(
                async_get_clientsession(hass),
                entry.data[CONF_HOST],
                entry.data[CONF_USERNAME],
                entry.data[CONF_PASSWORD],
            ),
            coordinator=coordinator,
        )
    except (OSError, aiohttp.ClientError) as e:
        raise ConfigEntryAuthFailed("Authentication failed") from e

    # Check if we got a different URL back -> Something is seriously wrong
    if entry.runtime_data.api.m2mUrl != entry.data["m2mUrl"]:
        raise ConfigEntryError(
            f"SMGW returned {entry.runtime_data.api.m2mUrl} but it was originally configured with {entry.data['m2mUrl']}!"
        )

    # Get initial data
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as e:
        raise ConfigEntryError("Failed to fetch initial data") from e

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ThebenConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
