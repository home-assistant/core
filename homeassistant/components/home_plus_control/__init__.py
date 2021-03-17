"""The Legrand Home+ Control integration."""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    dispatcher,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import api, config_flow, helpers
from .const import (
    API,
    CONF_SUBSCRIPTION_KEY,
    DATA_COORDINATOR,
    DISPATCHER_REMOVERS,
    DOMAIN,
    ENTITY_UIDS,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_REMOVE_ENTITIES,
)

# Configuration schema for component in configuration.yaml
CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_SUBSCRIPTION_KEY): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

# The Legrand Home+ Control platform is currently limited to "switch" entities
PLATFORMS = ["switch"]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Legrand Home+ Control component from configuration.yaml."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        _LOGGER.debug(
            "No config in configuration.yaml for the Legrand Home+ Control component"
        )
        return True

    # If there is a configuration section in configuration.yaml, then we add the data into
    # the hass.data object
    _LOGGER.debug("Configuring Legrand Home+ Control component from configuration.yaml")
    hass.data[DOMAIN]["config"] = config[DOMAIN]

    # Register the implementation from the config information
    config_flow.HomePlusControlFlowHandler.async_register_implementation(
        hass,
        helpers.HomePlusControlOAuth2Implementation(hass, config[DOMAIN]),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Legrand Home+ Control from a config entry."""
    hass_entry_data = hass.data[DOMAIN].setdefault(config_entry.entry_id, {})

    # Retrieve the registered implementation
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, config_entry
        )
    )

    # Using an aiohttp-based API lib, so rely on async framework
    # Add the API object to the domain's data in HA
    hass_entry_data[API] = api.HomePlusControlAsyncApi(
        hass, config_entry, implementation
    )

    # Dict of entity unique identifiers of this integration
    hass_entry_data[ENTITY_UIDS] = {}

    # Integration dispatchers
    hass_entry_data[DISPATCHER_REMOVERS] = [
        dispatcher.async_dispatcher_connect(
            hass, SIGNAL_ADD_ENTITIES, helpers.async_add_entities
        ),
        dispatcher.async_dispatcher_connect(
            hass, SIGNAL_REMOVE_ENTITIES, helpers.async_remove_entities
        ),
    ]

    # Register the Data Coordinator with the integration
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="home_plus_control_module",
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )
    hass_entry_data[DATA_COORDINATOR] = coordinator

    # Continue setting up the platform
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the Legrand Home+ Control config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        # Unsubscribe the config_entry signal dispatcher connections
        dispatcher_removers = hass.data[DOMAIN][config_entry.entry_id].pop(
            "dispatcher_removers"
        )
        for remover in dispatcher_removers:
            remover()

        # And finally unload the domain config entry data
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
