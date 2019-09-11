"""Support for Neato botvac connected vacuum cleaners."""
import logging
from datetime import timedelta
from urllib.error import HTTPError

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import discovery, config_validation as cv
from homeassistant.util import Throttle

from .const import (
    DOMAIN,
    CONF_VENDOR,
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

    conf = config.get(DOMAIN, CONFIG_SCHEMA({}))
    hass.data[DOMAIN] = {"config": conf}

    if DOMAIN not in config:
        # No config entry there
        return True

    # TODO: If everything is okay
    # TODO: Skip if already configured
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up config entry."""
    from pybotvac import Account, Neato, Vorwerk

    if entry.data[CONF_VENDOR] == "neato":
        hass.data[NEATO_LOGIN] = NeatoHub(hass, entry.data, Account, Neato)
    elif entry.data[CONF_VENDOR] == "vorwerk":
        hass.data[NEATO_LOGIN] = NeatoHub(hass, entry.data, Account, Vorwerk)

    hub = hass.data[NEATO_LOGIN]
    if not hub.login():
        _LOGGER.debug("Failed to login to Neato API")
        return False

    hub.update_robots()
    for component in ("camera", "vacuum", "switch"):
        discovery.load_platform(hass, component, DOMAIN, {}, entry.data)

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

        self.my_neato = neato(
            domain_config[CONF_USERNAME], domain_config[CONF_PASSWORD], vendor
        )
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
