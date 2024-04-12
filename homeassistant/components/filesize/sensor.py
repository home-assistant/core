"""Sensor for monitoring the size of a file."""

from __future__ import annotations

from datetime import datetime
import logging
import pathlib

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILE_PATH, EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FileSizeCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = (
    SensorEntityDescription(
        key="file",
        translation_key="size",
        native_unit_of_measurement=UnitOfInformation.MEGABYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="bytes",
        translation_key="size_bytes",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_updated",
        translation_key="last_updated",
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.TIMESTAMP,
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


class FilesizeEntity(CoordinatorEntity[FileSizeCoordinator], SensorEntity):
    """Filesize sensor."""

    _attr_has_entity_name = True

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
