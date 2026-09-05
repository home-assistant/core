"""The flo integration."""

import asyncio
import logging

from aioflo.api import API, async_get_api
from aioflo.errors import RequestError

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_USE_SSO
from .coordinator import FloConfigEntry, FloDeviceDataUpdateCoordinator, FloRuntimeData

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]


async def async_get_flo_api(
    hass: HomeAssistant,
    username: str,
    password: str,
    *,
    use_sso: bool = False,
) -> tuple[API, bool]:
    """Authenticate against Flo, falling back to Moen SSO if legacy auth fails.

    Returns the API client and whether SSO was used.
    """
    session = async_get_clientsession(hass)
    try:
        return (
            await async_get_api(username, password, session=session, use_sso=use_sso),
            use_sso,
        )
    except RequestError as err:
        if use_sso:
            raise
        _LOGGER.info("Legacy Flo auth failed (%s); retrying with Moen SSO", err)
        return (
            await async_get_api(username, password, session=session, use_sso=True),
            True,
        )


async def async_setup_entry(hass: HomeAssistant, entry: FloConfigEntry) -> bool:
    """Set up flo from a config entry."""
    try:
        client, used_sso = await async_get_flo_api(
            hass,
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            use_sso=entry.data.get(CONF_USE_SSO, False),
        )
    except RequestError as err:
        raise ConfigEntryNotReady from err

    if used_sso and not entry.data.get(CONF_USE_SSO):
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_USE_SSO: True}
        )

    user_info = await client.user.get_info(include_location_info=True)

    _LOGGER.debug("Flo user information with locations: %s", user_info)

    devices = [
        FloDeviceDataUpdateCoordinator(
            hass, entry, client, location["id"], device["id"]
        )
        for location in user_info["locations"]
        for device in location["devices"]
    ]

    tasks = [device.async_refresh() for device in devices]
    await asyncio.gather(*tasks)

    entry.runtime_data = FloRuntimeData(client=client, devices=devices)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FloConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
