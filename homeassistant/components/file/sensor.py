"""Support for sensor value(s) stored in local files."""
from __future__ import annotations

import logging
import os

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (
    CONF_FILE_PATH,
    CONF_NAME,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "File"

ICON = "mdi:file"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_FILE_PATH): cv.isfile,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the file sensor."""
    file_path = config[CONF_FILE_PATH]
    name = config[CONF_NAME]
    unit = config.get(CONF_UNIT_OF_MEASUREMENT)

    if (value_template := config.get(CONF_VALUE_TEMPLATE)) is not None:
        value_template.hass = hass

    if hass.config.is_allowed_path(file_path):
        async_add_entities([FileSensor(name, file_path, unit, value_template)], True)
    else:
        _LOGGER.error("'%s' is not an allowed directory", file_path)


class FileSensor(SensorEntity):
    """Implementation of a file sensor."""

    def __init__(self, name, file_path, unit_of_measurement, value_template):
        """Initialize the file sensor."""
        self._name = name
        self._file_path = file_path
        self._unit_of_measurement = unit_of_measurement
        self._val_tpl = value_template
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    def update(self):
        """Get the latest entry from a file and updates the state."""
        try:
            with open(self._file_path, encoding="utf-8") as file_data:
                for line in file_data:
                    data = line
                data = data.strip()
        except (IndexError, FileNotFoundError, IsADirectoryError, UnboundLocalError):
            _LOGGER.warning(
                "File or data not present at the moment: %s",
                os.path.basename(self._file_path),
            )
            return

        if self._val_tpl is not None:
            self._state = self._val_tpl.async_render_with_possible_json_value(
                data, None
            )
        else:
            self._state = data
