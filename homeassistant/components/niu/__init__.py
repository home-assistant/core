"""The NIU integration."""
import asyncio

from niu import NiuCloud  # , NiuAPIException
import voluptuous as vol
import logging

from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    ATTR_BATTERY_LEVEL,
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USERNAME,
)

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.discovery import load_platform

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    NIU_COMPONENTS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
                ): vol.All(cv.positive_int, vol.Clamp(min=MIN_SCAN_INTERVAL)),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, entry: config_entries.ConfigEntry):
    """Set up NIU from a config entry."""

    conf = entry.get(DOMAIN)

    hass.data[DOMAIN][entry.entry_id] = setup_account(hass, entry[DOMAIN])

    def update_data():
        try:
            hass.data[DOMAIN][entry.entry_id].update_vehicles()

            for listener in self._update_listeners:
                listener()
        except Exception as err:
            _LOGGER.error(f"Error communicating with NIU Cloud")
            _LOGGER.exception(err)

    update_data()

    for component in NIU_COMPONENTS:
        load_platform(hass, component, DOMAIN, {}, entry)

    return True


def setup_account(hass, conf: dict):
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]
    account = NiuAccount(username, password)

    try:
        account.connect()
    except Exception as err:
        _LOGGER.error(f"Error connecting to NIU Cloud")
        _LOGGER.exception(err)
        return False

    return account


class NiuAccount:
    def __init__(self, username, password):
        self.account = NiuCloud(username=username, password=password)
        self._update_listeners = []

    def update(self, *_):
        try:
            self.account.update_vehicles()
            for listener in self._update_listeners:
                listener()
        except Exception as err:
            _LOGGER.error("Could not update NIU data")
            _LOGGER.exception(err)

    def add_update_listener(self, listener):
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)
