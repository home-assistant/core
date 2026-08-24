"""One entity per served row; each is available independently."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from enum import IntEnum
from typing import cast, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import SofarConfigEntry, SofarDataUpdateCoordinator, SofarRuntimeData
from .entity import SofarEntity, SofarEntityDescription


def _enum_label(member_name: str) -> str:
    """Format an IntEnum member name to match an ENUM sensor option."""
    return " ".join(word.capitalize() for word in member_name.split("_"))


# How far below the high-water mark counts as a torn read (~0.003%
# observed here) vs a genuine reset — well under HA's 90% threshold.
_TOTAL_INCREASING_DIP_TOLERANCE = 0.01


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SofarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sofar Inverter Modbus sensor platform."""
    runtime_data = entry.runtime_data
    served = runtime_data.served_components

    entities: list[SensorEntity] = [
        (
            SofarTotalSensor
            if description.state_class
            in (SensorStateClass.TOTAL, SensorStateClass.TOTAL_INCREASING)
            else SofarSensor
        )(runtime_data, description)
        for description in SENSOR_DESCRIPTIONS
        if description.component in served
    ]
    readings = runtime_data.readings
    entities.extend(
        _SofarCommunicationHealthEntity(readings, description)
        for description in _COMMUNICATION_HEALTH_DESCRIPTIONS
    )
    async_add_entities(entities)


def _health_bucket(coordinator: SofarDataUpdateCoordinator) -> str:
    """Bucket success_rate into the communication_health ENUM options."""
    rate = coordinator.success_rate
    if rate is None:
        return "unknown"
    if rate == 100:
        return "good"
    if rate >= 80:
        return "degraded"
    return "poor"


@dataclass(frozen=True, kw_only=True)
class _CommunicationHealthDescription(SensorEntityDescription):
    """Computed from the coordinator, not tied to a device component."""

    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC
    value_fn: Callable[[SofarDataUpdateCoordinator], str | float | datetime | None]


_HEALTH_DESCRIPTION = _CommunicationHealthDescription(
    key="communication_health",
    translation_key="communication_health",
    device_class=SensorDeviceClass.ENUM,
    options=["good", "degraded", "poor", "unknown"],
    value_fn=_health_bucket,
)
_SUCCESS_RATE_DESCRIPTION = _CommunicationHealthDescription(
    key="communication_health_success_rate",
    translation_key="communication_health_success_rate",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda coordinator: coordinator.success_rate,
)
_LAST_ERROR_DESCRIPTION = _CommunicationHealthDescription(
    key="communication_health_last_error",
    translation_key="communication_health_last_error",
    entity_registry_enabled_default=False,
    value_fn=lambda coordinator: coordinator.last_error,
)
_LAST_ERROR_TIME_DESCRIPTION = _CommunicationHealthDescription(
    key="communication_health_last_error_time",
    translation_key="communication_health_last_error_time",
    device_class=SensorDeviceClass.TIMESTAMP,
    entity_registry_enabled_default=False,
    value_fn=lambda coordinator: coordinator.last_error_time,
)

_COMMUNICATION_HEALTH_DESCRIPTIONS: tuple[_CommunicationHealthDescription, ...] = (
    _HEALTH_DESCRIPTION,
    _SUCCESS_RATE_DESCRIPTION,
    _LAST_ERROR_DESCRIPTION,
    _LAST_ERROR_TIME_DESCRIPTION,
)


class _SofarCommunicationHealthEntity(
    CoordinatorEntity[SofarDataUpdateCoordinator], SensorEntity
):
    """Sensor computed from the coordinator; available even on a dead link."""

    _attr_has_entity_name = True
    entity_description: _CommunicationHealthDescription

    def __init__(
        self,
        coordinator: SofarDataUpdateCoordinator,
        description: _CommunicationHealthDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        serial = coordinator.device.serial_number
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def available(self) -> bool:
        return True

    @property
    @override
    def native_value(self) -> str | float | datetime | None:
        return self.entity_description.value_fn(self.coordinator)


class SofarSensor(SofarEntity, SensorEntity):
    """A read-only value off one of the device's components."""

    entity_description: SofarSensorDescription

    @property
    @override
    def native_value(self) -> str | int | float | date | None:
        component = getattr(self.coordinator.device, self.entity_description.component)
        value = getattr(component, self.entity_description.key)
        # IntEnum.__str__ prints just the int since Python 3.11 — translate
        # to the label the ENUM sensor's options declared.
        if isinstance(value, IntEnum):
            return _enum_label(value.name)
        return cast(str | int | float | date | None, value)


class SofarTotalSensor(SofarEntity, RestoreSensor):
    """A long-term stat, restored on startup so it's never unknown at boot."""

    entity_description: SofarSensorDescription

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        description: SofarSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(runtime_data, description)
        self._total_increasing_high_water: float | None = None

    @property
    @override
    def available(self) -> bool:
        # Unconditional: long-term stats survive a link drop or offline night.
        return True

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is not None:
            if last_data.native_value is not None:
                try:
                    val = float(str(last_data.native_value))
                    self._attr_native_value = val
                    self._total_increasing_high_water = val
                except ValueError, TypeError:
                    pass

    @property
    @override
    def native_value(self) -> int | float | None:
        component = getattr(self.coordinator.device, self.entity_description.component)
        value = getattr(component, self.entity_description.key)
        if value is not None:
            if (
                self.entity_description.state_class is SensorStateClass.TOTAL_INCREASING
                and isinstance(value, (int, float))
            ):
                self._attr_native_value = self._smoothed_total_increasing(float(value))
            elif isinstance(value, (int, float)):
                self._attr_native_value = value
        if isinstance(self._attr_native_value, (int, float)):
            return self._attr_native_value
        return None

    def _smoothed_total_increasing(self, value: float) -> float:
        """Hold at the high-water mark through a torn read; let a reset through."""
        high_water = self._total_increasing_high_water
        if (
            high_water is None
            or value >= high_water
            or value < high_water * (1 - _TOTAL_INCREASING_DIP_TOLERANCE)
        ):
            self._total_increasing_high_water = value
            return value
        return high_water


@dataclass(frozen=True, kw_only=True)
class SofarSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """A SensorEntityDescription bound to which Component the value comes from."""


SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = ()
