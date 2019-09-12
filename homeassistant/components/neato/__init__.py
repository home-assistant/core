"""Support for Neato botvac connected vacuum cleaners."""
import logging
from datetime import timedelta
from requests.exceptions import HTTPError

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery, config_validation as cv
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    CONF_VENDOR,
    NEATO_CONFIG,
    NEATO_LOGIN,
    NEATO_ROBOTS,
    NEATO_PERSISTENT_MAPS,
    NEATO_MAP_DATA,
)

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_VENDOR, default="neato"): vol.In(
                    ["neato", "vorwerk"]
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass, config):
    """Set up the Neato component."""

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config[DOMAIN]
            )
        )
    elif DOMAIN not in config:
        return True

    hass.data[NEATO_CONFIG] = config[DOMAIN]
    return True


async def async_setup_entry(hass, entry):
    """Set up config entry."""
    from pybotvac import Account, Neato, Vorwerk

    if entry.data[CONF_VENDOR] == "neato":
        hass.data[NEATO_LOGIN] = NeatoHub(hass, entry.data, Account, Neato)
    elif entry.data[CONF_VENDOR] == "vorwerk":
        hass.data[NEATO_LOGIN] = NeatoHub(hass, entry.data, Account, Vorwerk)

    hub = hass.data[NEATO_LOGIN]
    if not hub.logged_in:
        _LOGGER.debug("Failed to login to Neato API")
        return False

    hub.update_robots()

    for component in ("camera", "vacuum", "switch"):
        discovery.load_platform(hass, component, DOMAIN, {}, entry.data)

    # TODO: What's the difference here?
    # for component in ("camera", "vacuum", "switch"):
    #    hass.async_add_job(
    #        hass.config_entries.async_forward_entry_setup(entry, component)
    #    )

    return True


async def async_unload_entry(hass, entry):
    """Unload config entry."""
    try:
        hass.data.pop(NEATO_LOGIN)
        return True
    except KeyError:
        return False


class NeatoHub:
    """A My Neato hub wrapper class."""

    def __init__(self, hass, domain_config, neato, vendor):
        """Initialize the Neato hub."""
        self.config = domain_config
        self._neato = neato
        self._hass = hass
        self._vendor = vendor

        self.my_neato = None
        self.logged_in = self.login()

        if self.logged_in:
            self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
            self._hass.data[NEATO_PERSISTENT_MAPS] = self.my_neato.persistent_maps
            self._hass.data[NEATO_MAP_DATA] = self.my_neato.maps

    def login(self):
        """Login to My Neato."""
        try:
            _LOGGER.debug("Trying to connect to Neato API")
            self.my_neato = self._neato(
                self.config[CONF_USERNAME], self.config[CONF_PASSWORD], self._vendor
            )
            return True
        except HTTPError:
            _LOGGER.error("Unable to connect to Neato API")
            return False

    @Throttle(timedelta(seconds=300))
    def update_robots(self):
        """Update the robot states."""
        _LOGGER.debug("Running HUB.update_robots %s", self._hass.data[NEATO_ROBOTS])
        self._hass.data[NEATO_ROBOTS] = self.my_neato.robots
        self._hass.data[NEATO_PERSISTENT_MAPS] = self.my_neato.persistent_maps
        self._hass.data[NEATO_MAP_DATA] = self.my_neato.maps

    def download_map(self, url):
        """Download a new map image."""
        map_image_data = self.my_neato.get_map_image(url)
        return map_image_data
