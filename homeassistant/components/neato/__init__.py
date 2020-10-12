"""Support for Neato botvac connected vacuum cleaners."""
import asyncio
from datetime import timedelta
import logging

from pybotvac import Account, Neato, Vorwerk
from pybotvac.exceptions import NeatoException, NeatoLoginException, NeatoRobotException
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle

from .config_flow import NeatoConfigFlow
from .const import (
    CONF_VENDOR,
    NEATO_CONFIG,
    NEATO_DOMAIN,
    NEATO_LOGIN,
    NEATO_MAP_DATA,
    NEATO_PERSISTENT_MAPS,
    NEATO_ROBOTS,
    VALID_VENDORS,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        NEATO_DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_VENDOR, default="neato"): vol.In(VALID_VENDORS),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    """Set up the Neato component."""

    if NEATO_DOMAIN not in config:
        # There is an entry and nothing in configuration.yaml
        return True

    entries = hass.config_entries.async_entries(NEATO_DOMAIN)
    hass.data[NEATO_CONFIG] = config[NEATO_DOMAIN]

    if entries:
        # There is an entry and something in the configuration.yaml
        entry = entries[0]
        conf = config[NEATO_DOMAIN]
        if (
            entry.data[CONF_USERNAME] == conf[CONF_USERNAME]
            and entry.data[CONF_PASSWORD] == conf[CONF_PASSWORD]
            and entry.data[CONF_VENDOR] == conf[CONF_VENDOR]
        ):
            # The entry is not outdated
            return True

        # The entry is outdated
        error = await hass.async_add_executor_job(
            NeatoConfigFlow.try_login,
            conf[CONF_USERNAME],
            conf[CONF_PASSWORD],
            conf[CONF_VENDOR],
        )
        if error is not None:
            _LOGGER.error(error)
            return False

        # Update the entry
        hass.config_entries.async_update_entry(entry, data=config[NEATO_DOMAIN])
    else:
        # Create the new entry
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                NEATO_DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[NEATO_DOMAIN],
            )
        )

    return True


async def async_setup_entry(hass, entry):
    """Set up config entry."""
    hub = NeatoHub(hass, entry.data, Account)

    await hass.async_add_executor_job(hub.login)
    if not hub.logged_in:
        _LOGGER.debug("Failed to login to Neato API")
        return False

    try:
        await hass.async_add_executor_job(hub.update_robots)
    except NeatoRobotException as ex:
        _LOGGER.debug("Failed to connect to Neato API")
        raise ConfigEntryNotReady from ex

    hass.data[NEATO_LOGIN] = hub

    for component in ("camera", "vacuum", "switch", "sensor"):
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload config entry."""
    hass.data.pop(NEATO_LOGIN)
    await asyncio.gather(
        hass.config_entries.async_forward_entry_unload(entry, "camera"),
        hass.config_entries.async_forward_entry_unload(entry, "vacuum"),
        hass.config_entries.async_forward_entry_unload(entry, "switch"),
        hass.config_entries.async_forward_entry_unload(entry, "sensor"),
    )
    return True


class NeatoHub:
    """A My Neato hub wrapper class."""

    def __init__(self, hass, domain_config, neato):
        """Initialize the Neato hub."""
        self.config = domain_config
        self._neato = neato
        self._hass = hass

        if self.config[CONF_VENDOR] == "vorwerk":
            self._vendor = Vorwerk()
        else:  # Neato
            self._vendor = Neato()

        self.my_neato = None
        self.logged_in = False

    def login(self):
        """Login to My Neato."""
        _LOGGER.debug("Trying to connect to Neato API")
        try:
            self.my_neato = self._neato(
                self.config[CONF_USERNAME], self.config[CONF_PASSWORD], self._vendor
            )
        except NeatoException as ex:
            if isinstance(ex, NeatoLoginException):
                _LOGGER.error("Invalid credentials")
            else:
                _LOGGER.error("Unable to connect to Neato API")
                raise ConfigEntryNotReady from ex
            self.logged_in = False
            return

        self.logged_in = True
        _LOGGER.debug("Successfully connected to Neato API")

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
