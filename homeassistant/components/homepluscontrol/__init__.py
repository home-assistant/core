"""The Legrand Home+ Control integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api, config_flow
from .const import CONF_REDIRECT_URI, CONF_SUBSCRIPTION_KEY, DOMAIN
from .helpers import HomePlusControlOAuth2Implementation

# Configuration schema for component in configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_SUBSCRIPTION_KEY): cv.string,
                vol.Required(CONF_REDIRECT_URI): cv.url,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# The Legrand Home+ Control platform is currently limited to "switch" entities
PLATFORMS = ["switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Legrand Home+ Control component from configuration.yaml."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        _LOGGER.debug(
            "No config in configuration.yaml for the Legrand Home+ Control component."
        )
        return True

    # If there is a configuration section in configuration.yaml, then we add the data into
    # the hass.data object
    _LOGGER.debug(
        "Configuring Legrand Home+ Control conmponent from configuration.yaml."
    )
    hass.data[DOMAIN]["config"] = config[DOMAIN]

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Set up Legrand Home+ Control from a config entry."""

    _LOGGER.debug("Configuring Legrand Home+ Control component from ConfigEntry")

    # Register the implementation from the config entry
    config_flow.HomePlusControlFlowHandler.async_register_implementation(
        hass,
        HomePlusControlOAuth2Implementation(hass, config_entry.data),
    )

    # Retrieve the registered implementation
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )

    # Using an aiohttp-based API lib, so rely on async framework
    # Add the API object to the domain's data in HA
    hass.data[DOMAIN][config_entry.entry_id] = api.HomePlusControlAsyncApi(
        hass, config_entry, implementation
    )

    # Continue setting up the platform
    _LOGGER.debug("Hass config components %s", hass.config.components)
    for component in PLATFORMS:
        _LOGGER.debug("Configuring %s", component)
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )
    _LOGGER.debug("Hass config components %s", hass.config.components)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    """Unload the Legrand Home+ Control config entry."""
    _LOGGER.debug("Unloading the Legrand Home+ Control component and config entry.")
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id, None)
        # await api.close_connection() - No closing of the HA aiohttp session here
        # _LOGGER.debug("Legrand Home+ Control API connection closed.")

        # Unsubscribe the config_entry update listener
        remover = hass.data[DOMAIN].pop("options_listener_remover", None)
        if remover is not None:
            remover()

        _LOGGER.debug("Legrand Home+ Control config entry unloaded.")

    return unload_ok
