"""Sensor for displaying the number of result from Flume."""
from datetime import timedelta
import logging

from pyflume import FlumeData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    DEFAULT_NAME,
    DOMAIN,
    FLUME_DEVICES,
    FLUME_HTTP_SESSION,
    FLUME_TOKEN_FULL_PATH,
    FLUME_TYPE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Optional(CONF_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Import the platform into a config entry."""

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=config
        )
    )


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Flume sensor."""

    flume_domain_data = hass.data[DOMAIN][config_entry.entry_id]

    flume_token_full_path = flume_domain_data[FLUME_TOKEN_FULL_PATH]
    http_session = flume_domain_data[FLUME_HTTP_SESSION]
    flume_devices = flume_domain_data[FLUME_DEVICES]

    config = config_entry.data
    time_zone = str(hass.config.time_zone)
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    name = config.get(CONF_NAME, DEFAULT_NAME)

    flume_entity_list = []
    for device in flume_devices.device_list:
        if device["type"] != FLUME_TYPE_SENSOR:
            continue

        device_id = device["id"]
        device_name = device["location"]["name"]

        flume = FlumeData(
            username,
            password,
            client_id,
            client_secret,
            device_id,
            time_zone,
            SCAN_INTERVAL,
            flume_token_full_path,
            update_on_init=False,
            http_session=http_session,
        )
        flume_entity_list.append(FlumeSensor(flume, f"{name} {device_name}", device_id))

    if flume_entity_list:
        # Flume takes a while to setup currently
        # which will be fixed upstream.  To prevent
        # Home Assistant from blocking on startup
        # we do not do a poll on add.
        async_add_entities(flume_entity_list, False)


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
    def device_info(self):
        """Device info for the flume sensor."""
        return {
            "name": self._name,
            "identifiers": {(DOMAIN, self._device_id)},
            "manufacturer": "Flume, Inc.",
            "model": "Flume Smart Water Monitor",
        }

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
        return self._device_id

    def update(self):
        """Get the latest data and updates the states."""
        self._available = False
        self.flume.update()
        new_value = self.flume.value
        if new_value is not None:
            self._available = True
            self._state = new_value
