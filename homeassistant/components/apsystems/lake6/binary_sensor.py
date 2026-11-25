"""Binary sensor platform for the APsystems Lake_6 integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import Lake6ConfigEntry, Lake6Coordinator, Lake6Data
from .entity import Lake6Entity


@dataclass(frozen=True, kw_only=True)
class Lake6BinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Lake_6 alarm bit.

    Every alarm is "0" (normal) or "1" (fault) on the wire; the client already
    converted them to bool, so `is_on` only has to pick the field.
    """

    is_on: Callable[[Lake6Data], bool | None]


BINARY_SENSORS: tuple[Lake6BinarySensorEntityDescription, ...] = (
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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: Lake6ConfigEntry,
    add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Lake_6 binary sensor platform."""
    coordinator = config_entry.runtime_data.coordinator
    add_entities(
        Lake6BinarySensorEntity(coordinator, description)
        for description in BINARY_SENSORS
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
