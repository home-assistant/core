"""The Legrand Home+ Control integration."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
from homepluscontrol.homeplusapi import HomePlusControlApiError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    config_entry_oauth2_flow,
    config_validation as cv,
    dispatcher,
)
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import config_flow, helpers
from .api import HomePlusControlAsyncApi
from .const import (
    API,
    CONF_SUBSCRIPTION_KEY,
    DATA_COORDINATOR,
    DISPATCHER_REMOVERS,
    DOMAIN,
    ENTITY_UIDS,
    SIGNAL_ADD_ENTITIES,
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
        return True

    # Register the implementation from the config information
    config_flow.HomePlusControlFlowHandler.async_register_implementation(
        hass,
        helpers.HomePlusControlOAuth2Implementation(hass, config[DOMAIN]),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Legrand Home+ Control from a config entry."""
    hass_entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})

    # Retrieve the registered implementation
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    # Using an aiohttp-based API lib, so rely on async framework
    # Add the API object to the domain's data in HA
    api = hass_entry_data[API] = HomePlusControlAsyncApi(hass, entry, implementation)

    # Set of entity unique identifiers of this integration
    uids = hass_entry_data[ENTITY_UIDS] = set()

    # Integration dispatchers
    hass_entry_data[DISPATCHER_REMOVERS] = []

    device_registry = async_get_device_registry(hass)

    # Register the Data Coordinator with the integration
    async def async_update_data():
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        try:
            # Note: asyncio.TimeoutError and aiohttp.ClientError are already
            # handled by the data update coordinator.
            async with async_timeout.timeout(10):
                module_data = await api.async_get_modules()
        except HomePlusControlApiError as err:
            raise UpdateFailed(
                f"Error communicating with API: {err} [{type(err)}]"
            ) from err

        # Remove obsolete entities from Home Assistant
        entity_uids_to_remove = uids - set(module_data)
        for uid in entity_uids_to_remove:
            uids.remove(uid)
            device = device_registry.async_get_device({(DOMAIN, uid)})
            device_registry.async_remove_device(device.id)

        # Send out signal for new entity addition to Home Assistant
        new_entity_uids = set(module_data) - uids
        if new_entity_uids:
            uids.update(new_entity_uids)
            dispatcher.async_dispatcher_send(
                hass,
                SIGNAL_ADD_ENTITIES,
                new_entity_uids,
                coordinator,
            )

        return module_data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        # Name of the data. For logging purposes.
        name="home_plus_control_module",
        update_method=async_update_data,
        # Polling interval. Will only be polled if there are subscribers.
        update_interval=timedelta(seconds=60),
    )
    hass_entry_data[DATA_COORDINATOR] = coordinator

    async def start_platforms():
        """Continue setting up the platforms."""
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_setup(entry, platform)
                for platform in PLATFORMS
            ]
        )
        # Only refresh the coordinator after all platforms are loaded.
        await coordinator.async_refresh()

    hass.async_create_task(start_platforms())

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload the Legrand Home+ Control config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
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
