"""Support for Neato botvac connected vacuum cleaners."""
import asyncio
from datetime import timedelta
import logging

from pybotvac import Account, Neato
from pybotvac.exceptions import NeatoException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

from . import api, config_flow
from .const import (
    NEATO_CONFIG,
    NEATO_DOMAIN,
    NEATO_LOGIN,
    NEATO_MAP_DATA,
    NEATO_PERSISTENT_MAPS,
    NEATO_ROBOTS,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        NEATO_DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = ["camera", "vacuum", "switch", "sensor"]


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up the Neato component."""
    hass.data[NEATO_DOMAIN] = {}

    if NEATO_DOMAIN not in config:
        return True

    hass.data[NEATO_CONFIG] = config[NEATO_DOMAIN]
    vendor = Neato()
    config_flow.OAuth2FlowHandler.async_register_implementation(
        hass,
        api.NeatoImplementation(
            hass,
            NEATO_DOMAIN,
            config[NEATO_DOMAIN][CONF_CLIENT_ID],
            config[NEATO_DOMAIN][CONF_CLIENT_SECRET],
            vendor.auth_endpoint,
            vendor.token_endpoint,
        ),
    )

    return True


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version < 2:
        _LOGGER.warning(
            "Your configuration is outdated. Please delete the integration and add neato botvac again."
        )
        return False

    _LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    neato_session = api.ConfigEntryAuth(hass, entry, session)
    hass.data[NEATO_DOMAIN][entry.entry_id] = neato_session
    hub = NeatoHub(hass, Account(neato_session))

    try:
        await hass.async_add_executor_job(hub.update_robots)
    except NeatoException as ex:
        _LOGGER.debug("Failed to connect to Neato API")
        raise ConfigEntryNotReady from ex

    hass.data[NEATO_LOGIN] = hub

    for component in ("camera", "vacuum", "switch", "sensor"):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigType) -> bool:
    """Unload config entry."""
    unload_ok = all(
        await asyncio.gather(
            hass.config_entries.async_forward_entry_unload(entry, "camera"),
            hass.config_entries.async_forward_entry_unload(entry, "vacuum"),
            hass.config_entries.async_forward_entry_unload(entry, "switch"),
            hass.config_entries.async_forward_entry_unload(entry, "sensor"),
        )
    )
    if unload_ok:
        hass.data[NEATO_DOMAIN].pop(entry.entry_id)

    return unload_ok


class NeatoHub:
    """A My Neato hub wrapper class."""

    def __init__(self, hass: HomeAssistantType, neato: Account):
        """Initialize the Neato hub."""
        self._hass: HomeAssistantType = hass
        self.my_neato: Account = neato

    @Throttle(timedelta(minutes=1))
    def update_robots(self):
        """Update the robot states."""
        _LOGGER.debug("Running HUB.update_robots %s", self._hass.data.get(NEATO_ROBOTS))
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
        self._hass.data[NEATO_PERSISTENT_MAPS] = self.my_neato.persistent_maps
        self._hass.data[NEATO_MAP_DATA] = self.my_neato.maps

    def download_map(self, url):
        """Download a new map image."""
        map_image_data = self.my_neato.get_map_image(url)
        return map_image_data
