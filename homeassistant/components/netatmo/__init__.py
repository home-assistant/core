"""The Netatmo integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DISCOVERY,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import AUTH, DATA_PERSONS, DOMAIN, OAUTH2_AUTHORIZE, OAUTH2_TOKEN

_LOGGER = logging.getLogger(__name__)

CONF_SECRET_KEY = "secret_key"
CONF_WEBHOOKS = "webhooks"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                cv.deprecated(CONF_SECRET_KEY): cv.match_all,
                cv.deprecated(CONF_USERNAME): cv.match_all,
                cv.deprecated(CONF_WEBHOOKS): cv.match_all,
                cv.deprecated(CONF_DISCOVERY): cv.match_all,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["binary_sensor", "camera", "climate", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Netatmo component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_PERSONS] = {}

    if DOMAIN not in config:
        return True

    config_flow.NetatmoFlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Netatmo from a config entry."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    hass.data[DOMAIN][entry.entry_id] = {
        AUTH: api.ConfigEntryNetatmoAuth(hass, entry, implementation)
    }

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
