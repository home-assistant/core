"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
import logging

from pyflume import FlumeData, FlumeDeviceList
from requests import Session
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Flume Sensor"

CONF_EXCLUDE_DEVICES = "exclude_devices"
CONF_INCLUDE_DEVICES = "include_devices"


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
        vol.Optional(CONF_EXCLUDE_DEVICES): cv.ensure_list,
        vol.Optional(CONF_INCLUDE_DEVICES): cv.ensure_list,
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
    include_devices = [
        str(device_id) for device_id in config.get(CONF_INCLUDE_DEVICES, [])
    ]
    exclude_devices = [
        str(device_id) for device_id in config.get(CONF_EXCLUDE_DEVICES, [])
    ]
    flume_entity_list = []

    http_session = Session()

    flume_devices = FlumeDeviceList(
        username,
        password,
        client_id,
        client_secret,
        flume_token_file,
        http_session=http_session,
    )

    for device in flume_devices.device_list:
        if device["type"] == FLUME_TYPE_SENSOR:
            device_id = device["id"]
            device_name = device["location"]["name"]
            if exclude_devices and str(device_id) in exclude_devices:
                _LOGGER.info(
                    "Skipping device %s (%s) because it is in exclude_devices",
                    device_id,
                    device_name,
                )
                continue
            if include_devices and str(device_id) not in include_devices:
                _LOGGER.info(
                    "Skipping device %s (%s) because it is not in include_devices",
                    device_id,
                    device_name,
                )
                continue

            flume = FlumeData(
                username,
                password,
                client_id,
                client_secret,
                device_id,
                time_zone,
                SCAN_INTERVAL,
                flume_token_file,
                update_on_init=False,
                http_session=http_session,
            )
            flume_entity_list.append(
                FlumeSensor(flume, f"{name} {device_name}", device_id)
            )

    if flume_entity_list:
        add_entities(flume_entity_list, True)


class FlumeSensor(Entity):
    """Representation of the Flume sensor."""

    def __init__(self, flume, name, device_id):
        """Initialize the Flume sensor."""
        self.flume = flume
        self._name = name
        self._device_id = device_id
        self._state = None
        self._available = False

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
        # This is in gallons per SCAN_INTERVAL
        return "gal/m"

    @property
    def available(self):
        """Device is available."""
        return self._available

    @property
    def unique_id(self):
        """Device unique ID."""
        return f"Flume {self._device_id}"

    @property
    def device_state_attributes(self):
        """Return the device specific state attributes."""
        return {"device_id": self._device_id}

    def update(self):
        """Get the latest data and updates the states."""
        self._available = False
        self.flume.update()
        new_value = self.flume.value
        if new_value is not None:
            self._available = True
            self._state = new_value
