"""The Netatmo integration."""

# TODO:
# * fix webhooks

import asyncio
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.helpers import config_validation as cv, config_entry_oauth2_flow
from homeassistant.config_entries import ConfigEntry

from .const import (
    AUTH,
    CONF_PUBLIC,
    DATA_PERSONS,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from . import api, config_flow

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# PLATFORMS = ["binary_sensor", "camera", "climate", "light", "sensor", "switch"]
PLATFORMS = ["binary_sensor", "camera", "climate", "light", "sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Netatmo component."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][DATA_PERSONS] = {}
    hass.data[DOMAIN][CONF_PUBLIC] = config.get("sensor", {})

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
    # Backwards compat
    if "auth_implementation" not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_implementation": DOMAIN}
        )

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    hass.data[DOMAIN][AUTH] = api.ConfigEntryNetatmoAuth(hass, entry, implementation)

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
        hass.data[DOMAIN].pop(AUTH)

    return unload_ok
