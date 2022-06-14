"""Sensor for monitoring the size of a file."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
import os
import pathlib

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, DATA_BYTES, DATA_MEGABYTES
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ICON = "mdi:file"

SENSOR_TYPES = (
    SensorEntityDescription(
        key="file",
        icon=ICON,
        name="Size",
        native_unit_of_measurement=DATA_MEGABYTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bytes",
        entity_registry_enabled_default=False,
        icon=ICON,
        name="Size bytes",
        native_unit_of_measurement=DATA_BYTES,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_updated",
        entity_registry_enabled_default=False,
        icon=ICON,
        name="Last Updated",
        device_class=SensorDeviceClass.TIMESTAMP,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the platform from config entry."""

    path = entry.data[CONF_FILE_PATH]
    get_path = await hass.async_add_executor_job(pathlib.Path, path)
    fullpath = str(get_path.absolute())

    coordinator = FileSizeCoordinator(hass, fullpath)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        FilesizeEntity(description, fullpath, entry.entry_id, coordinator)
        for description in SENSOR_TYPES
    )


class FileSizeCoordinator(DataUpdateCoordinator):
    """Filesize coordinator."""

    def __init__(self, hass: HomeAssistant, path: str) -> None:
        """Initialize filesize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self._path = path

    async def _async_update_data(self) -> dict[str, float | int | datetime]:
        """Fetch file information."""
        try:
            statinfo = await self.hass.async_add_executor_job(os.stat, self._path)
        except OSError as error:
            raise UpdateFailed(f"Can not retrieve file statistics {error}") from error

        size = statinfo.st_size
        last_updated = datetime.utcfromtimestamp(statinfo.st_mtime).replace(
            tzinfo=dt_util.UTC
        )

        _LOGGER.debug("size %s, last updated %s", size, last_updated)
        data: dict[str, int | float | datetime] = {
            "file": round(size / 1e6, 2),
            "bytes": size,
            "last_updated": last_updated,
        }

        return data


class FilesizeEntity(CoordinatorEntity[FileSizeCoordinator], SensorEntity):
    """Filesize sensor."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        description: SensorEntityDescription,
        path: str,
        entry_id: str,
        coordinator: FileSizeCoordinator,
    ) -> None:
        """Initialize the Filesize sensor."""
        super().__init__(coordinator)
        base_name = path.split("/")[-1]
        self._attr_name = f"{base_name} {description.name}"
        self._attr_unique_id = (
            entry_id if description.key == "file" else f"{entry_id}-{description.key}"
        )
        self.entity_description = description
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry_id)},
            name=base_name,
        )

    @property
    def native_value(self) -> float | int | datetime:
        """Return the value of the sensor."""
        value: float | int | datetime = self.coordinator.data[
            self.entity_description.key
        ]
        return value
