"""Sensor for monitoring the contents of a folder."""

from datetime import timedelta
import glob
import os

import probatio

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_FILTER, CONF_FOLDER_PATHS, DEFAULT_FILTER, DOMAIN

BREAKS_IN_HA_VERSION = "2027.5.0"
INTEGRATION_TITLE = "Folder"

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
    """Import the YAML sensor platform into a config entry."""
    path: str = config[CONF_FOLDER_PATHS]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )

    if (
        result["type"] is FlowResultType.ABORT
        and (reason := result["reason"]) != "already_configured"
    ):
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"deprecated_yaml_import_issue_{reason}_{path}",
            breaks_in_ha_version=BREAKS_IN_HA_VERSION,
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=ir.IssueSeverity.WARNING,
            translation_key=f"deprecated_yaml_import_issue_{reason}",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": INTEGRATION_TITLE,
                "path": path,
                "config_variable": "allowlist_external_dirs",
            },
        )
        return

    ir.async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{DOMAIN}",
        breaks_in_ha_version=BREAKS_IN_HA_VERSION,
        is_fixable=False,
        issue_domain=DOMAIN,
        severity=ir.IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": DOMAIN,
            "integration_title": INTEGRATION_TITLE,
        },
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the folder sensor from a config entry."""
    async_add_entities(
        [
            Folder(
                entry.options[CONF_FOLDER_PATHS],
                entry.options[CONF_FILTER],
                entry.entry_id,
            )
        ],
        True,
    )


class Folder(SensorEntity):
    """Representation of a folder."""

    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_has_entity_name = True
    _attr_icon = "mdi:folder"
    _attr_name = None
    _attr_native_unit_of_measurement = UnitOfInformation.MEGABYTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, folder_path: str, filter_term: str, entry_id: str) -> None:
        """Initialize the data object."""
        folder_path = os.path.join(folder_path, "")  # If no trailing / add it
        self._folder_path = folder_path
        self._filter_term = filter_term
        self._attr_unique_id = entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=os.path.split(os.path.split(folder_path)[0])[1],
        )

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
