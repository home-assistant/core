"""Sensor platform for Home Assistant Backup integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LastBackupState
from .coordinator import BackupConfigEntry, BackupCoordinatorData
from .entity import BackupManagerEntity
from .manager import BackupManagerState


@dataclass(kw_only=True, frozen=True)
class BackupSensorEntityDescription(SensorEntityDescription):
    """Description for Home Assistant Backup sensor entities."""

    value_fn: Callable[[BackupCoordinatorData], str | datetime | None]


BACKUP_MANAGER_DESCRIPTIONS = (
    BackupSensorEntityDescription(
        key="backup_manager_state",
        translation_key="backup_manager_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in BackupManagerState],
        value_fn=lambda data: data.backup_manager_state,
    ),
    BackupSensorEntityDescription(
        key="next_scheduled_automatic_backup",
        translation_key="next_scheduled_automatic_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.next_scheduled_automatic_backup,
    ),
    BackupSensorEntityDescription(
        key="last_successful_automatic_backup",
        translation_key="last_successful_automatic_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_successful_automatic_backup,
    ),
    BackupSensorEntityDescription(
        key="last_attempted_automatic_backup",
        translation_key="last_attempted_automatic_backup",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.last_attempted_automatic_backup,
    ),
    BackupSensorEntityDescription(
        key="last_backup_state",
        translation_key="last_backup_state",
        device_class=SensorDeviceClass.ENUM,
        options=[state.value for state in LastBackupState],
        value_fn=lambda data: data.last_backup_state,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BackupConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Sensor set up for backup config entry."""

    coordinator = config_entry.runtime_data

    async_add_entities(
        BackupManagerSensor(coordinator, description)
        for description in BACKUP_MANAGER_DESCRIPTIONS
    )


class BackupManagerSensor(BackupManagerEntity, SensorEntity):
    """Sensor to track backup manager state."""

    entity_description: BackupSensorEntityDescription

    @property
    def native_value(self) -> str | datetime | None:
        """Return native value of entity."""
        return self.entity_description.value_fn(self.coordinator.data)
