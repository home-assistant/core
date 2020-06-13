"""Sensor for monitoring the size of a file."""
import datetime
import logging
import os

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import DATA_BYTES, DATA_MEGABYTES
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
import homeassistant.util.data_size as data_size
from homeassistant.helpers.reload import setup_reload_service

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


CONF_FILE_PATHS = "file_paths"
CONF_UNIT_OF_MEASUREMENT = "unit"
ICON = "mdi:file"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILE_PATHS): vol.All(cv.ensure_list, [cv.isfile]),
        vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=DATA_MEGABYTES): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the file size sensor."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

    sensors = []
    for path in config.get(CONF_FILE_PATHS):
        if not hass.config.is_allowed_path(path):
            _LOGGER.error(
                "Filepath %s is not valid or allowed. Check directory whitelisting.",
                path,
            )
            continue
        sensors.append(Filesize(path, config.get(CONF_UNIT_OF_MEASUREMENT)))

    if sensors:
        add_entities(sensors, True)


class Filesize(Entity):
    """Encapsulates file size information."""

    def __init__(self, path, unit_of_measurement):
        """Initialize the data object."""
        self._path = path  # Need to check it's a valid path
        self._size = None
        self._last_updated = None
        self._name = path.split("/")[-1]
        self._unit_of_measurement = unit_of_measurement

    def update(self):
        """Update the sensor."""
        statinfo = os.stat(self._path)
        self._size = statinfo.st_size
        last_updated = datetime.datetime.fromtimestamp(statinfo.st_mtime)
        self._last_updated = last_updated.isoformat()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the size of the file."""
        return round(
            data_size.convert(self._size, DATA_BYTES, self._unit_of_measurement), 2
        )

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return other details about the sensor state."""
        return {
            "path": self._path,
            "last_updated": self._last_updated,
            "bytes": self._size,
        }

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement
