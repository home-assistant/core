"""Linky Atome."""
import logging
import voluptuous as vol

from datetime import timedelta
from pyatome.client import AtomeClient
from pyatome.client import PyAtomeError

from homeassistant.const import (
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_NAME,
    DEVICE_CLASS_POWER,
    POWER_WATT,
)

from homeassistant.components.sensor import PLATFORM_SCHEMA

from homeassistant.helpers.entity import Entity

from homeassistant.util import Throttle

import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "atome"

SCAN_INTERVAL = timedelta(seconds=30)
SESSION_RENEW_INTERVAL = timedelta(minutes=55)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor."""
    name = config[CONF_NAME]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    try:
        client = AtomeClient(username, password)
    except PyAtomeError as exp:
        _LOGGER.error(exp)
        return

    add_entities([AtomeSensor(name, client)], True)


class AtomeSensor(Entity):
    """Representation of a sensor entity for Atome."""

    def __init__(self, name, client: AtomeClient):
        """Initialize the sensor."""
        self._name = name

        self._client = client

        self._attributes = None
        self._state = None
        self._login()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name or DEFAULT_NAME

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return POWER_WATT

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_POWER

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @Throttle(SESSION_RENEW_INTERVAL)
    def _login(self):
        """Login to Atome API, create session."""
        self._client.login()

    def _get_data(self):
        """Retrieve live data."""
        return self._client.get_live()

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Update device state."""

        try:
            values = self._get_data()
            self._state = values["last"]
            _LOGGER.debug("Updating atome data. Got: %d", self._state)

        except KeyError as error:
            _LOGGER.error("Missing last value in values: %s: %s", values, error)
