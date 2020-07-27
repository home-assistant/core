"""Shark IQ Integration."""

import asyncio
import logging

import async_timeout
from datetime import timedelta
from sharkiqpy import AylaApi, SharkIqAuthError, get_ayla_api
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import COMPONENTS, DOMAIN, SHARKIQ_SESSION

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)
SCAN_INTERVAL = timedelta(seconds=5)


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


async def async_setup(hass, config):
    """Set up the sharkiq environment."""
    hass.data.setdefault(DOMAIN, {})
    if DOMAIN not in config:
        return True
    for index, conf in enumerate(config[DOMAIN]):
        _LOGGER.debug(
            "Importing Shark IQ #%d (Username: %s)", index, conf[CONF_USERNAME]
        )
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=conf,
            )
        )


async def async_connect_or_timeout(ayla_api: AylaApi) -> AylaApi:
    """Connect to vacuum."""
    try:
        with async_timeout.timeout(10):
            _LOGGER.debug("Initialize connection to Ayla networks API")
            await ayla_api.async_sign_in()
    except SharkIqAuthError as exc:
        _LOGGER.error("Error to connect to Shark IQ api")
        raise CannotConnect from exc
    except asyncio.TimeoutError as exc:
        _LOGGER.error("Timeout expired")
        raise CannotConnect from exc

    return ayla_api


async def async_setup_entry(hass, config_entry):
    """Set the config entry up."""

    # Set up sharkiq platforms with config entry.
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

    hass.data[DOMAIN][config_entry.entry_id] = {SHARKIQ_SESSION: ayla_api}

    for component in COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    if not config_entry.update_listeners:
        config_entry.add_update_listener(async_update_options)

    return True


async def async_disconnect_or_timeout(ayla_api):
    """Disconnect to vacuum."""
    _LOGGER.debug("Disconnecting from Ayla Api")
    with async_timeout.timeout(3):
        await ayla_api.async_sign_out()
    return True


async def async_update_options(hass, config_entry):
    """Update options."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in COMPONENTS
            ]
        )
    )
    if unload_ok:
        domain_data = hass.data[DOMAIN][config_entry.entry_id]
        await async_disconnect_or_timeout(ayla_api=domain_data[SHARKIQ_SESSION])
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
