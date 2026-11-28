"""The read-only binary sensors for APsystems local API integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from APsystemsEZ1 import ReturnAlarmInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    ApSystemsConfigEntry,
    ApSystemsData,
    ApSystemsDataCoordinator,
    Lake6Coordinator,
    Lake6Data,
    Lake6RuntimeData,
)
from .entity import ApSystemsEntity, Lake6Entity


@dataclass(frozen=True, kw_only=True)
class ApsystemsLocalApiBinarySensorDescription(BinarySensorEntityDescription):
    """Describes Apsystens Inverter binary sensor entity."""

    is_on: Callable[[ReturnAlarmInfo], bool | None]


BINARY_SENSORS: tuple[ApsystemsLocalApiBinarySensorDescription, ...] = (
    ApsystemsLocalApiBinarySensorDescription(
        key="off_grid_status",
        translation_key="off_grid_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda c: c.offgrid,
    ),
    ApsystemsLocalApiBinarySensorDescription(
        key="dc_1_short_circuit_error_status",
        translation_key="dc_1_short_circuit_error_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda c: c.shortcircuit_1,
    ),
    ApsystemsLocalApiBinarySensorDescription(
        key="dc_2_short_circuit_error_status",
        translation_key="dc_2_short_circuit_error_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda c: c.shortcircuit_2,
    ),
    ApsystemsLocalApiBinarySensorDescription(
        key="output_fault_status",
        translation_key="output_fault_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda c: not c.operating,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    config = config_entry.runtime_data
    if isinstance(config, Lake6RuntimeData):
        add_entities(
            Lake6BinarySensorEntity(config.coordinator, description)
            for description in LAKE6_BINARY_SENSORS
        )
        return

    add_entities(
        ApSystemsBinarySensorWithDescription(
            data=config,
            entity_description=desc,
        )
        for desc in BINARY_SENSORS
    )


class ApSystemsBinarySensorWithDescription(
    CoordinatorEntity[ApSystemsDataCoordinator], ApSystemsEntity, BinarySensorEntity
):
    """Base binary sensor to be used with description."""

    entity_description: ApsystemsLocalApiBinarySensorDescription

    def __init__(
        self,
        data: ApSystemsData,
        entity_description: ApsystemsLocalApiBinarySensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(data.coordinator)
        ApSystemsEntity.__init__(self, data)
        self.entity_description = entity_description
        self._attr_unique_id = f"{data.device_id}_{entity_description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return value of sensor."""
        return self.entity_description.is_on(self.coordinator.data.alarm_info)


@dataclass(frozen=True, kw_only=True)
class Lake6BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Lake_6 alarm bit.

    Every alarm is "0" (normal) or "1" (fault) on the wire; the client already
    converted them to bool, so `is_on` only has to pick the field.
    """

    is_on: Callable[[Lake6Data], bool | None]


LAKE6_BINARY_SENSORS: tuple[Lake6BinarySensorEntityDescription, ...] = (
    Lake6BinarySensorEntityDescription(
        key="battery_over_temperature",
        translation_key="battery_over_temperature",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_over_temperature,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_under_temperature",
        translation_key="battery_under_temperature",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_under_temperature,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_communication_error",
        translation_key="battery_communication_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_communication_error,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_over_voltage",
        translation_key="battery_over_voltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_over_voltage,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_under_voltage",
        translation_key="battery_under_voltage",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_under_voltage,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_over_current",
        translation_key="battery_over_current",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_over_current,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_internal_error",
        translation_key="battery_internal_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_internal_error,
    ),
    # dev_temp in /alarms is a temperature protection alarm bit, not the
    # temperature reading of the same name in /energies.
    Lake6BinarySensorEntityDescription(
        key="device_temperature_protection",
        translation_key="device_temperature_protection",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.device_temperature_protection,
    ),
    Lake6BinarySensorEntityDescription(
        key="device_system_error",
        translation_key="device_system_error",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.device_system_error,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_shutdown",
        translation_key="battery_shutdown",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_shutdown,
    ),
    Lake6BinarySensorEntityDescription(
        key="grid_anomaly",
        translation_key="grid_anomaly",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.grid_anomaly,
    ),
    Lake6BinarySensorEntityDescription(
        key="offgrid_over_current",
        translation_key="offgrid_over_current",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.offgrid_over_current,
    ),
    Lake6BinarySensorEntityDescription(
        key="offgrid_short_circuit",
        translation_key="offgrid_short_circuit",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.offgrid_short_circuit,
    ),
    Lake6BinarySensorEntityDescription(
        key="battery_calibration",
        translation_key="battery_calibration",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on=lambda d: d.alarms.battery_calibration,
    ),
)


class Lake6BinarySensorEntity(Lake6Entity, BinarySensorEntity):
    """A binary sensor backed by one Lake_6 alarm bit."""

    entity_description: Lake6BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: Lake6Coordinator,
        entity_description: Lake6BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = f"{self.device_id}_{entity_description.key}"

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True when the alarm bit is set."""
        return self.entity_description.is_on(self.coordinator.data)
