"""Support for Synology Surveillance Station Cameras."""
import logging
from typing import Any

import requests
from synology.surveillance_station import SurveillanceStation
import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Synology Surveillance Home Mode Switch"
DEFAULT_TIMEOUT = 5

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None) -> None:
    """Set up a Synology Surveillance Station Home Mode Toggle."""
    verify_ssl = config.get(CONF_VERIFY_SSL)
    timeout = config.get(CONF_TIMEOUT)
    name = config.get(CONF_NAME)

    try:
        surveillance = SurveillanceStation(
            config.get(CONF_URL),
            config.get(CONF_USERNAME),
            config.get(CONF_PASSWORD),
            verify_ssl=verify_ssl,
            timeout=timeout,
        )
    except (requests.exceptions.RequestException, ValueError):
        _LOGGER.exception("Error when initializing SurveillanceStation", exc_info=True)
        return False

    devices = []
    device = HomeModeSwitch(surveillance, name)
    devices.append(device)

    add_entities(devices)


class HomeModeSwitch(SwitchDevice):
    """Synology Surveillance Station Home Mode toggle."""

    def __init__(self, surveillance, name):
        """Initialize a Home Mode toggle."""
        super().__init__()
        self._surveillance = surveillance
        self._name = name

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return True if Home Mode is enabled."""
        try:
            return self._surveillance.get_home_mode_status()
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to get the status", exc_info=True)
            return False

    def turn_on(self, **kwargs: Any) -> None:
        """Enable Home Mode."""
        try:
            self._surveillance.set_home_mode(True)
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to enable home mode", exc_info=True)

    def turn_off(self, **kwargs: Any) -> None:
        """Disable Home Mode."""
        try:
            self._surveillance.set_home_mode(False)
        except (requests.exceptions.RequestException):
            _LOGGER.exception("Error when trying to disable home mode", exc_info=True)
