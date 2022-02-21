"""Sensor for monitoring the size of a file."""
from __future__ import annotations

import datetime
import logging
import os
import pathlib

import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as PARENT_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import DATA_MEGABYTES
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


CONF_FILE_PATHS = "file_paths"
ICON = "mdi:file"

PLATFORM_SCHEMA = PARENT_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_FILE_PATHS): vol.All(cv.ensure_list, [cv.isfile])}
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the file size sensor."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

    sensors = []
    paths = set()
    for path in config[CONF_FILE_PATHS]:
        try:
            fullpath = str(pathlib.Path(path).absolute())
        except OSError as error:
            _LOGGER.error("Can not access file %s, error %s", path, error)
            continue

        if fullpath in paths:
            continue
        paths.add(fullpath)

        if not hass.config.is_allowed_path(path):
            _LOGGER.error("Filepath %s is not valid or allowed", path)
            continue

        sensors.append(Filesize(fullpath))

    if sensors:
        add_entities(sensors, True)


class Filesize(SensorEntity):
    """Encapsulates file size information."""

    _attr_native_unit_of_measurement = DATA_MEGABYTES
    _attr_icon = ICON

    def __init__(self, path: str) -> None:
        """Initialize the data object."""
        self._path = path  # Need to check its a valid path
        self._attr_name = path.split("/")[-1]

    def update(self) -> None:
        """Update the sensor."""
        try:
            statinfo = os.stat(self._path)
        except OSError as error:
            _LOGGER.error("Can not retrieve file statistics %s", error)
            self._attr_native_value = None
            return

        size = statinfo.st_size
        last_updated = datetime.datetime.fromtimestamp(statinfo.st_mtime).isoformat()
        self._attr_native_value = round(size / 1e6, 2) if size else None
        self._attr_extra_state_attributes = {
            "path": self._path,
            "last_updated": last_updated,
            "bytes": size,
        }
