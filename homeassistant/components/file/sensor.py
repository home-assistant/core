"""Support for sensor value(s) stored in local files."""
from __future__ import annotations

import logging
import os

from file_read_backwards import FileReadBackwards
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
from homeassistant.helpers.template import Template
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
    file_path: str = config[CONF_FILE_PATH]
    name: str = config[CONF_NAME]
    unit: str | None = config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template: Template | None = config.get(CONF_VALUE_TEMPLATE)

    if value_template is not None:
        value_template.hass = hass

    if hass.config.is_allowed_path(file_path):
        async_add_entities([FileSensor(name, file_path, unit, value_template)], True)
    else:
        _LOGGER.error("'%s' is not an allowed directory", file_path)


class FileSensor(SensorEntity):
    """Implementation of a file sensor."""

    _attr_icon = ICON

    def __init__(
        self,
        name: str,
        file_path: str,
        unit_of_measurement: str | None,
        value_template: Template | None,
    ) -> None:
        """Initialize the file sensor."""
        self._attr_name = name
        self._file_path = file_path
        self._attr_native_unit_of_measurement = unit_of_measurement
        self._val_tpl = value_template

    def update(self):
        """Get the latest entry from a file and updates the state."""
        try:
            with FileReadBackwards(self._file_path, encoding="utf-8") as file_data:
                for line in file_data:
                    data = line
                    break
                data = data.strip()
        except (IndexError, FileNotFoundError, IsADirectoryError, UnboundLocalError):
            _LOGGER.warning(
                "File or data not present at the moment: %s",
                os.path.basename(self._file_path),
            )
            return

        if self._val_tpl is not None:
            self._attr_native_value = (
                self._val_tpl.async_render_with_possible_json_value(data, None)
            )
        else:
            self._attr_native_value = data
