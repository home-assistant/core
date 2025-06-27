"""Sensors for OneDrive."""

from collections.abc import Callable
from dataclasses import dataclass

from onedrive_personal_sdk.const import DriveState
from onedrive_personal_sdk.models.items import DriveQuota

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OneDriveConfigEntry, OneDriveUpdateCoordinator

PARALLEL_UPDATES = 0


@dataclass(kw_only=True, frozen=True)
class OneDriveSensorEntityDescription(SensorEntityDescription):
    """Describes OneDrive sensor entity."""

    value_fn: Callable[[DriveQuota], StateType]


DRIVE_STATE_ENTITIES: tuple[OneDriveSensorEntityDescription, ...] = (
    OneDriveSensorEntityDescription(
        key="total_size",
        value_fn=lambda quota: quota.total,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=0,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    OneDriveSensorEntityDescription(
        key="used_size",
        value_fn=lambda quota: quota.used,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OneDriveSensorEntityDescription(
        key="remaining_size",
        value_fn=lambda quota: quota.remaining,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.DATA_SIZE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    OneDriveSensorEntityDescription(
        key="drive_state",
        value_fn=lambda quota: quota.state.value,
        options=[state.value for state in DriveState],
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OneDriveConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up OneDrive sensors based on a config entry."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        OneDriveDriveStateSensor(coordinator, description)
        for description in DRIVE_STATE_ENTITIES
    )


class OneDriveDriveStateSensor(
    CoordinatorEntity[OneDriveUpdateCoordinator], SensorEntity
):
    """Define a OneDrive sensor."""

    entity_description: OneDriveSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OneDriveUpdateCoordinator,
        description: OneDriveSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_unique_id = f"{coordinator.data.id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            name=coordinator.data.name or coordinator.config_entry.title,
            identifiers={(DOMAIN, coordinator.data.id)},
            manufacturer="Microsoft",
            model=f"OneDrive {coordinator.data.drive_type.value.capitalize()}",
            configuration_url=f"https://onedrive.live.com/?id=root&cid={coordinator.data.id}",
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        assert self.coordinator.data.quota
        return self.entity_description.value_fn(self.coordinator.data.quota)

    @property
    def available(self) -> bool:
        """Availability of the sensor."""
        return super().available and self.coordinator.data.quota is not None
