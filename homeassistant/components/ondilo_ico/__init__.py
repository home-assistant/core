"""The Ondilo ICO integration."""
import asyncio

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import DOMAIN, OAUTH2_CLIENTID, OAUTH2_CLIENTSECRET
from .oauth_impl import OndiloOauth2Implementation

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_CLIENT_ID, default=OAUTH2_CLIENTID): cv.string,
                vol.Optional(
                    CONF_CLIENT_SECRET, default=OAUTH2_CLIENTSECRET
                ): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Ondilo ICO component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass, OndiloOauth2Implementation(hass),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Ondilo ICO from a config entry."""
    # Ondilo config entry is always the same as Client_id and secret cannot be changed.
    # So defining those values here to avoid asking users to always configure same values

    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass, OndiloOauth2Implementation(hass),
    )

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    hass.data[DOMAIN][entry.entry_id] = api.OndiloClient(hass, entry, implementation)

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
