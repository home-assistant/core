"""Support for TRMNL sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from trmnl.models import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TRMNLConfigEntry
from .coordinator import TRMNLCoordinator
from .entity import TRMNLEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class TRMNLSensorEntityDescription(SensorEntityDescription):
    """Describes a TRMNL sensor entity."""

    value_fn: Callable[[Device], int | float | None]


SENSOR_DESCRIPTIONS: tuple[TRMNLSensorEntityDescription, ...] = (
    TRMNLSensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda device: device.percent_charged,
    ),
    TRMNLSensorEntityDescription(
        key="battery_voltage",
        translation_key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.battery_voltage,
    ),
    TRMNLSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.rssi,
    ),
    TRMNLSensorEntityDescription(
        key="wifi_strength",
        translation_key="wifi_strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda device: device.wifi_strength,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TRMNLConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TRMNL sensor entities based on a config entry."""
    coordinator = entry.runtime_data

    known_device_ids: set[int] = set()

    def _async_entity_listener() -> None:
        new_ids = set(coordinator.data) - known_device_ids
        if new_ids:
            async_add_entities(
                TRMNLSensor(coordinator, device_id, description)
                for device_id in new_ids
                for description in SENSOR_DESCRIPTIONS
            )
            known_device_ids.update(new_ids)

    entry.async_on_unload(coordinator.async_add_listener(_async_entity_listener))
    _async_entity_listener()


class TRMNLSensor(TRMNLEntity, SensorEntity):
    """Defines a TRMNL sensor."""

    entity_description: TRMNLSensorEntityDescription

    def __init__(
        self,
        coordinator: TRMNLCoordinator,
        device_id: int,
        description: TRMNLSensorEntityDescription,
    ) -> None:
        """Initialize TRMNL sensor."""
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> int | float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._device)
