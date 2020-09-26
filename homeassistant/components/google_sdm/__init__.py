"""The google_sdm integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import (
    CONF_CLIENT_EMAIL,
    CONF_PRIVATE_KEY,
    CONF_PROJECT_ID,
    CONF_SERVICE_ACCOUNT,
    CONF_SUBSCRIPTION,
    DATA_CONFIG,
    DOMAIN,
    OAUTH2_AUTHORIZE_TEMPLATE,
    OAUTH2_TOKEN,
)

GOOGLE_SERVICE_ACCOUNT = vol.Schema(
    {
        vol.Required(CONF_PRIVATE_KEY): cv.string,
        vol.Required(CONF_CLIENT_EMAIL): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_PROJECT_ID): cv.string,
                vol.Required(CONF_SUBSCRIPTION): cv.string,
                vol.Required(CONF_SERVICE_ACCOUNT): GOOGLE_SERVICE_ACCOUNT,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["climate"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the google_sdm component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    hass.data[DOMAIN][DATA_CONFIG] = config[DOMAIN]
    project_id = config[DOMAIN][CONF_PROJECT_ID]

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            OAUTH2_AUTHORIZE_TEMPLATE.format(project_id),
            OAUTH2_TOKEN,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up google_sdm from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    hass.data[DOMAIN][entry.entry_id] = api.ConfigEntryAuth(
        hass,
        entry,
        session,
        hass.data[DOMAIN][DATA_CONFIG][CONF_PROJECT_ID],
        hass.data[DOMAIN][DATA_CONFIG][CONF_SERVICE_ACCOUNT],
        hass.data[DOMAIN][DATA_CONFIG][CONF_SUBSCRIPTION],
    )

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    _LOGGER.debug("async_setup_entry is done")

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
