"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
import logging

from pyflume import FlumeData, FlumeDeviceList
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Flume Sensor"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
FLUME_TYPE_SENSOR = 2

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Flume sensor."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    flume_token_file = hass.config.path("FLUME_TOKEN_FILE")
    time_zone = str(hass.config.time_zone)
    name = config[CONF_NAME]
    flume_entity_list = []

    flume_devices = FlumeDeviceList(
        username, password, client_id, client_secret, flume_token_file
    )

    for device in flume_devices.device_list:
        if device["type"] == FLUME_TYPE_SENSOR:
            flume = FlumeData(
                username,
                password,
                client_id,
                client_secret,
                device["id"],
                time_zone,
                SCAN_INTERVAL,
                flume_token_file,
            )
            flume_entity_list.append(FlumeSensor(flume, f"{name} {device['id']}"))

    if flume_entity_list:
        add_entities(flume_entity_list, True)


class FlumeSensor(Entity):
    """Representation of the Flume sensor."""

    def __init__(self, flume, name):
        """Initialize the Flume sensor."""
        self.flume = flume
        self._name = name
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return "gal"

    def update(self):
        """Get the latest data and updates the states."""
        self.flume.update()
        self._state = self.flume.value
