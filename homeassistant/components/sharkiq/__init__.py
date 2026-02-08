"""Shark IQ Integration."""

import asyncio
from contextlib import suppress

import aiohttp
from sharkiq import (
    AylaApi,
    SharkIqAuthError,
    SharkIqAuthExpiringError,
    SharkIqNotAuthedError,
    get_ayla_api,
)

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType

from .const import (
    API_TIMEOUT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
)
from .coordinator import SharkIqUpdateCoordinator
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def async_connect_or_timeout(ayla_api: AylaApi) -> bool:
    """Connect to vacuum."""
    try:
        async with asyncio.timeout(API_TIMEOUT):
            LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except SharkIqAuthError:
        LOGGER.error("Authentication error connecting to Shark IQ api")
        return False
    except TimeoutError as exc:
        LOGGER.error("Timeout expired")
        raise CannotConnect from exc

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the component."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Initialize the sharkiq platform via config entry."""
    if CONF_REGION not in config_entry.data:
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_REGION: SHARKIQ_REGION_DEFAULT},
        )

    new_websession = async_create_clientsession(
        hass,
        cookie_jar=aiohttp.CookieJar(unsafe=True, quote_cookie=False),
    )

    ayla_api = get_ayla_api(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        websession=new_websession,
        europe=(config_entry.data[CONF_REGION] == SHARKIQ_REGION_EUROPE),
    )

    try:
        if not await async_connect_or_timeout(ayla_api):
            return False
    except CannotConnect as exc:
        raise exceptions.ConfigEntryNotReady from exc

    shark_vacs = await ayla_api.async_get_devices(False)
    device_names = ", ".join(d.name for d in shark_vacs)
    LOGGER.debug("Found %d Shark IQ device(s): %s", len(shark_vacs), device_names)
    coordinator = SharkIqUpdateCoordinator(hass, config_entry, ayla_api, shark_vacs)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_disconnect_or_timeout(coordinator: SharkIqUpdateCoordinator):
    """Disconnect to vacuum."""
    LOGGER.debug("Disconnecting from Ayla Api")
    async with asyncio.timeout(5):
        with suppress(
            SharkIqAuthError, SharkIqAuthExpiringError, SharkIqNotAuthedError
        ):
            await coordinator.ayla_api.async_sign_out()


async def async_update_options(hass: HomeAssistant, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
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
