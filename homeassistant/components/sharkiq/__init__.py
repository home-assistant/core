"""Shark IQ Integration."""

import asyncio
from contextlib import suppress

import async_timeout
from sharkiqpy import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    get_ayla_api,
)

from homeassistant import exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import _LOGGER, API_TIMEOUT, DOMAIN, PLATFORMS
from .update_coordinator import SharkIqUpdateCoordinator


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def async_connect_or_timeout(ayla_api: AylaApi) -> bool:
    """Connect to vacuum."""
    try:
        with async_timeout.timeout(API_TIMEOUT):
            _LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except SharkIqAuthError:
        _LOGGER.error("Authentication error connecting to Shark IQ api")
        return False
    except asyncio.TimeoutError as exc:
        _LOGGER.error("Timeout expired")
        raise CannotConnect from exc

    return True


async def async_setup_entry(hass, config_entry):
    """Initialize the sharkiq platform via config entry."""
    ayla_api = get_ayla_api(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        websession=hass.helpers.aiohttp_client.async_get_clientsession(),
    )

    try:
        if not await async_connect_or_timeout(ayla_api):
            return False
    except CannotConnect as exc:
        raise exceptions.ConfigEntryNotReady from exc

    shark_vacs = await ayla_api.async_get_devices(False)
    device_names = ", ".join(d.name for d in shark_vacs)
    _LOGGER.debug("Found %d Shark IQ device(s): %s", len(shark_vacs), device_names)
    coordinator = SharkIqUpdateCoordinator(hass, config_entry, ayla_api, shark_vacs)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_disconnect_or_timeout(coordinator: SharkIqUpdateCoordinator):
    """Disconnect to vacuum."""
    _LOGGER.debug("Disconnecting from Ayla Api")
    with async_timeout.timeout(5), suppress(
        SharkIqAuthError, SharkIqAuthExpiringError, SharkIqNotAuthedError
    ):
        await coordinator.ayla_api.async_sign_out()


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        domain_data = hass.data[DOMAIN][config_entry.entry_id]
        with suppress(SharkIqAuthError):
            await async_disconnect_or_timeout(coordinator=domain_data)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
