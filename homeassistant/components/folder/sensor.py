"""Sensor for monitoring the contents of a folder."""

from datetime import timedelta
import glob
import logging
import os

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_FOLDER_PATHS = "folder"
CONF_FILTER = "filter"
DEFAULT_FILTER = "*"

SCAN_INTERVAL = timedelta(minutes=1)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(CONF_FOLDER_PATHS): cv.isdir,
        probatio.Optional(CONF_FILTER, default=DEFAULT_FILTER): cv.string,
    }
)


def get_files_list(folder_path: str, filter_term: str) -> list[str]:
    """Return the list of files, applying filter."""
    query = folder_path + filter_term
    return glob.glob(query)


def get_size(files_list: list[str]) -> int:
    """Return the sum of the size in bytes of files in the list."""
    size_list = [os.stat(f).st_size for f in files_list if os.path.isfile(f)]
    return sum(size_list)


def get_files_and_size(folder_path: str, filter_term: str) -> tuple[list[str], int]:
    """Return the filtered list of files and their total size in bytes."""
    files_list = get_files_list(folder_path, filter_term)
    return files_list, get_size(files_list)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the folder sensor."""
    path: str = config[CONF_FOLDER_PATHS]

    if not await hass.async_add_executor_job(hass.config.is_allowed_path, path):
        _LOGGER.error("Folder %s is not valid or allowed", path)
    else:
        folder = Folder(path, config[CONF_FILTER])
        async_add_entities([folder], True)


class Folder(SensorEntity):
    """Representation of a folder."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_icon = "mdi:folder"
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES

    def __init__(self, folder_path: str, filter_term: str) -> None:
        """Initialize the data object."""
        folder_path = os.path.join(folder_path, "")  # If no trailing / add it
        self._folder_path = folder_path  # Need to check its a valid path
        self._filter_term = filter_term
        self._attr_name = os.path.split(os.path.split(folder_path)[0])[1]

    async def async_update(self) -> None:
        """Update the sensor."""
        files_list, size = await self.hass.async_add_executor_job(
            get_files_and_size, self._folder_path, self._filter_term
        )
        number_of_files = len(files_list)

        self._attr_native_value = round(size / 1e6, 2)
        self._attr_extra_state_attributes = {
            "path": self._folder_path,
            "filter": self._filter_term,
            "number_of_files": number_of_files,
            "bytes": size,
            "file_list": files_list,
        }
