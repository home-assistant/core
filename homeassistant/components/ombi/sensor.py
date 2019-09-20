"""Support for Ombi."""
from datetime import timedelta
import logging

import pyombi
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_URLBASE = "urlbase"

DEFAULT_PORT = 5000
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_SSL = False
DEFAULT_URLBASE = ""

SENSOR_TYPES = {
    "movies": {"type": "Movie requests", "icon": "mdi:movie"},
    "tv": {"type": "TV show requests", "icon": "mdi:television-classic"},
    "pending": {"type": "Pending requests", "icon": "mdi:clock-alert-outline"},
    "approved": {"type": "Approved requests", "icon": "mdi:check"},
    "available": {"type": "Available requests", "icon": "mdi:download"},
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_URLBASE, default=DEFAULT_URLBASE): cv.string,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=list(SENSOR_TYPES)): vol.All(
            cv.ensure_list, [vol.In(list(SENSOR_TYPES))]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ombi sensor platform."""
    conditions = config[CONF_MONITORED_CONDITIONS]

    urlbase = f"{config[CONF_URLBASE].strip('/') if config[CONF_URLBASE] else ''}/"

    ombi = pyombi.Ombi(
        ssl=config[CONF_SSL],
        host=config[CONF_HOST],
        port=config[CONF_PORT],
        api_key=config[CONF_API_KEY],
        urlbase=urlbase,
    )

    try:
        ombi.test_connection()
    except pyombi.OmbiError as err:
        _LOGGER.warning("Unable to setup Ombi: %s", err)
        return

    sensors = []

    for condition in conditions:
        sensor_label = condition
        sensor_type = SENSOR_TYPES[condition].get("type")
        sensor_icon = SENSOR_TYPES[condition].get("icon")
        sensors.append(OmbiSensor(sensor_label, sensor_type, ombi, sensor_icon))

    add_entities(sensors, True)


class OmbiSensor(Entity):
    """Representation of an Ombi sensor."""

    def __init__(self, label, sensor_type, ombi, icon):
        """Initialize the sensor."""
        self._state = None
        self._label = label
        self._type = sensor_type
        self._ombi = ombi
        self._icon = icon

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Ombi {self._type}"

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return self._icon

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Update the sensor."""
        try:
            if self._label == "pending":
                self._state = self._ombi.pending_requests
            elif self._label == "movies":
                self._state = self._ombi.movie_requests
            elif self._label == "tv":
                self._state = self._ombi.tv_requests
            elif self._label == "approved":
                self._state = self._ombi.approved_requests
            elif self._label == "available":
                self._state = self._ombi.available_requests
        except pyombi.OmbiError as err:
            _LOGGER.warning("Unable to update Ombi sensor: %s", err)
            self._state = None
            return
