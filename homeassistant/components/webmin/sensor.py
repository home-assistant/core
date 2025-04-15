"""Support for Webmin sensors."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import WebminConfigEntry
from .coordinator import WebminUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class WebminFSSensorDescription(SensorEntityDescription):
    """Represents a filesystem sensor description."""

    mountpoint: str


SENSOR_TYPES: list[SensorEntityDescription] = [
    SensorEntityDescription(
        key="load_1m",
        translation_key="load_1m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="load_5m",
        translation_key="load_5m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="load_15m",
        translation_key="load_15m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="mem_total",
        translation_key="mem_total",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="mem_free",
        translation_key="mem_free",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="swap_total",
        translation_key="swap_total",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="swap_free",
        translation_key="swap_free",
        native_unit_of_measurement=UnitOfInformation.KIBIBYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="disk_total",
        translation_key="disk_total",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="disk_free",
        translation_key="disk_free",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key="disk_used",
        translation_key="disk_used",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
]


def generate_filesystem_sensor_description(
    mountpoint: str,
) -> list[WebminFSSensorDescription]:
    """Return all sensor descriptions for a mount point."""

    return [
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="total",
            translation_key="disk_fs_total",
            native_unit_of_measurement=UnitOfInformation.BYTES,
            suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
            device_class=SensorDeviceClass.DATA_SIZE,
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="used",
            translation_key="disk_fs_used",
            native_unit_of_measurement=UnitOfInformation.BYTES,
            suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
            device_class=SensorDeviceClass.DATA_SIZE,
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="free",
            translation_key="disk_fs_free",
            native_unit_of_measurement=UnitOfInformation.BYTES,
            suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
            device_class=SensorDeviceClass.DATA_SIZE,
            suggested_display_precision=1,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="itotal",
            translation_key="disk_fs_itotal",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="iused",
            translation_key="disk_fs_iused",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="ifree",
            translation_key="disk_fs_ifree",
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="used_percent",
            translation_key="disk_fs_used_percent",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
        WebminFSSensorDescription(
            mountpoint=mountpoint,
            key="iused_percent",
            translation_key="disk_fs_iused_percent",
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_registry_enabled_default=False,
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WebminConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Webmin sensors based on a config entry."""
    coordinator = entry.runtime_data

    entities: list[WebminSensor | WebminFSSensor] = [
        WebminSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.key in coordinator.data
    ]

    for fs, values in coordinator.data["disk_fs"].items():
        entities += [
            WebminFSSensor(coordinator, description)
            for description in generate_filesystem_sensor_description(fs)
            if description.key in values
        ]

    async_add_entities(entities)


class WebminSensor(CoordinatorEntity[WebminUpdateCoordinator], SensorEntity):
    """Represents a Webmin sensor."""

    entity_description: SensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WebminUpdateCoordinator, description: SensorEntityDescription
    ) -> None:
        """Initialize a Webmin sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.unique_id}_{description.key}"

    @property
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.coordinator.data[self.entity_description.key]


class WebminFSSensor(CoordinatorEntity[WebminUpdateCoordinator], SensorEntity):
    """Represents a Webmin filesystem sensor."""

    entity_description: WebminFSSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WebminUpdateCoordinator,
        description: WebminFSSensorDescription,
    ) -> None:
        """Initialize a Webmin filesystem sensor."""

        super().__init__(coordinator)
        self.entity_description = description
        self._attr_device_info = coordinator.device_info
        self._attr_translation_placeholders = {"mountpoint": description.mountpoint}
        self._attr_unique_id = (
            f"{coordinator.mac_address}_{description.mountpoint}_{description.key}"
        )

    @property
    def native_value(self) -> int | float:
        """Return the state of the sensor."""
        return self.coordinator.data["disk_fs"][self.entity_description.mountpoint][
            self.entity_description.key
        ]
