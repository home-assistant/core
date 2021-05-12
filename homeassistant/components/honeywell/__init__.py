"""Support for Honeywell (US) Total Connect Comfort climate systems."""
from datetime import timedelta
import logging

import requests
import somecomfort
import voluptuous as vol

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import Throttle

from .const import (
    CONF_COOL_AWAY_TEMPERATURE,
    CONF_DEV_ID,
    CONF_HEAT_AWAY_TEMPERATURE,
    CONF_LOC_ID,
    DEFAULT_COOL_AWAY_TEMPERATURE,
    DEFAULT_HEAT_AWAY_TEMPERATURE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(
                    CONF_COOL_AWAY_TEMPERATURE, default=DEFAULT_COOL_AWAY_TEMPERATURE
                ): vol.Coerce(int),
                vol.Optional(
                    CONF_HEAT_AWAY_TEMPERATURE, default=DEFAULT_HEAT_AWAY_TEMPERATURE
                ): vol.Coerce(int),
                vol.Optional(CONF_DEV_ID): cv.string,
                vol.Optional(CONF_LOC_ID): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def setup(hass: HomeAssistant, config: ConfigType):
    """Set up the Honeywell thermostat."""
    username = config[DOMAIN][CONF_USERNAME]
    password = config[DOMAIN][CONF_PASSWORD]

    try:
        client = somecomfort.SomeComfort(username, password)
    except somecomfort.AuthError:
        _LOGGER.error("Failed to login to honeywell account %s", username)
        return
    except somecomfort.SomeComfortError:
        _LOGGER.error(
            "Failed to initialize the Honeywell client: "
            "Check your configuration (username, password), "
            "or maybe you have exceeded the API rate limit?"
        )
        return

    loc_id = config[DOMAIN].get(CONF_LOC_ID)
    dev_id = config[DOMAIN].get(CONF_DEV_ID)

    for location in client.locations_by_id.values():
        for device in location.devices_by_id.values():
            if (not loc_id or location.locationid == loc_id) and (
                not dev_id or device.deviceid == dev_id
            ):
                hass.data[DOMAIN] = {}
                hass.data[DOMAIN]["device"] = device
                load_platform(hass, "climate", DOMAIN, config[DOMAIN], config)
                load_platform(hass, "sensor", DOMAIN, {}, config)

    return True


class HoneywellService:
    """Get the latest data and update."""

    def __init__(self, client, username, password):
        """Initialize the data object."""
        self._client = client
        self._username = username
        self._password = password
        self._device = None
        self.update()

    def _retry(self) -> bool:
        """Recreate a new somecomfort client.

        When we got an error, the best way to be sure that the next query
        will succeed, is to recreate a new somecomfort client.
        """
        try:
            self._client = somecomfort.SomeComfort(self._username, self._password)
        except somecomfort.AuthError:
            _LOGGER.error("Failed to login to honeywell account %s", self._username)
            return False
        except somecomfort.SomeComfortError as ex:
            _LOGGER.error("Failed to initialize honeywell client: %s", str(ex))
            return False

        devices = [
            device
            for location in self._client.locations_by_id.values()
            for device in location.devices_by_id.values()
            if device.name == self._device.name
        ]

        if len(devices) != 1:
            _LOGGER.error("Failed to find device %s", self._device.name)
            return False

        self._device = devices[0]
        return True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Update the state."""
        retries = 3
        while retries > 0:
            try:
                self._device.refresh()
                break
            except (
                somecomfort.client.APIRateLimited,
                OSError,
                requests.exceptions.ReadTimeout,
            ) as exp:
                retries -= 1
                if retries == 0:
                    raise exp
                if not self._retry():
                    raise exp
                _LOGGER.error("SomeComfort update failed, Retrying - Error: %s", exp)

        _LOGGER.debug(
            "latestData = %s ", self._device._data  # pylint: disable=protected-access
        )
