"""Shark IQ Integration."""

import asyncio
import urllib.parse
from contextlib import suppress
from sharkiq import Auth0Client

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
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    API_TIMEOUT,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    SHARKIQ_REGION_DEFAULT,
    SHARKIQ_REGION_EUROPE,
    SHARKIQ_REGION_ELSEWHERE,
)
from .coordinator import SharkIqUpdateCoordinator


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""




# ------------------------------
# Setup / teardown
# ------------------------------
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Initialize the SharkIQ platform via config entry."""

    session = async_create_clientsession(hass)

    # ---- Region handling with legacy support ----
    region = config_entry.data.get(CONF_REGION, SHARKIQ_REGION_DEFAULT)
    if region not in (SHARKIQ_REGION_EUROPE, SHARKIQ_REGION_ELSEWHERE):
        LOGGER.warning("Unknown region '%s' in config entry, defaulting to 'elsewhere'", region)
        hass.config_entries.async_update_entry(
            config_entry,
            data={**config_entry.data, CONF_REGION: SHARKIQ_REGION_ELSEWHERE},
        )
        region = SHARKIQ_REGION_ELSEWHERE

    europe = (region == SHARKIQ_REGION_EUROPE)

    # ---- Auth0 validation ----
    try:
        tokens = await Auth0Client.do_auth0_login(session, data[CONF_USERNAME], data[CONF_PASSWORD])
        LOGGER.debug("Got tokens during setup: %s", list(tokens.keys()))
    except Exception as exc:
        LOGGER.error("Auth0 login failed: %s", exc)
        raise exceptions.ConfigEntryNotReady from exc

    # ---- Initialize Ayla API client ----
    ayla_api = get_ayla_api(
        username=config_entry.data[CONF_USERNAME],
        password=config_entry.data[CONF_PASSWORD],
        websession=session,
        europe=europe,
    )

    try:
        async with asyncio.timeout(API_TIMEOUT):
            # Needed to fully authenticate the client for device discovery
            await ayla_api.async_set_cookie()
            await ayla_api.async_sign_in()
    except TimeoutError as exc:
        LOGGER.error("Timeout expired during Ayla API auth")
        raise CannotConnect from exc

    # ---- Discover devices ----
    shark_vacs = await ayla_api.async_get_devices(False)
    device_names = ", ".join(d.name for d in shark_vacs)
    LOGGER.debug("Found %d Shark IQ device(s): %s", len(shark_vacs), device_names)

    # ---- Coordinator setup ----
    coordinator = SharkIqUpdateCoordinator(hass, config_entry, ayla_api, shark_vacs)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_disconnect_or_timeout(coordinator: SharkIqUpdateCoordinator):
    """Disconnect from vacuum."""
    LOGGER.debug("Disconnecting from Ayla API")
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
    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
    if unload_ok:
        domain_data = hass.data[DOMAIN][config_entry.entry_id]
        with suppress(SharkIqAuthError):
            await async_disconnect_or_timeout(coordinator=domain_data)
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
