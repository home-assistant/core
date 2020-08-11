"""The JuiceNet integration."""
import asyncio
from datetime import timedelta
import logging

import aiohttp
from pyjuicenet import Api, TokenError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, JUICENET_API, JUICENET_COORDINATOR
from .device import JuiceNetApi

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the JuiceNet component."""
    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up JuiceNet from a config entry."""

    config = entry.data

    session = async_get_clientsession(hass)

    access_token = config[CONF_ACCESS_TOKEN]
    api = Api(access_token, session)

    juicenet = JuiceNetApi(api)

    try:
        await juicenet.setup()
    except TokenError as error:
        _LOGGER.error("JuiceNet Error %s", error)
        return False
    except aiohttp.ClientError as error:
        _LOGGER.error("Could not reach the JuiceNet API %s", error)
        raise ConfigEntryNotReady

    if not juicenet.devices:
        _LOGGER.error("No JuiceNet devices found for this account")
        return False
    _LOGGER.info("%d JuiceNet device(s) found", len(juicenet.devices))

    async def async_update_data():
        """Update all device states from the JuiceNet API."""
        for device in juicenet.devices:
            await device.update_state(True)
        return True

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="JuiceNet",
        update_method=async_update_data,
        update_interval=timedelta(seconds=30),
    )

    hass.data[DOMAIN][entry.entry_id] = {
        JUICENET_API: juicenet,
        JUICENET_COORDINATOR: coordinator,
    }

    await coordinator.async_refresh()

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
