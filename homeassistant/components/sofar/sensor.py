"""One entity per served row; each is available independently."""

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
from .entity import SofarEntity, build_device_info


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
    entities.append(SofarCommunicationHealthSensor(readings))
    entities.append(SofarCommunicationHealthSuccessRateSensor(readings))
    entities.append(SofarCommunicationHealthLastErrorSensor(readings))
    entities.append(SofarCommunicationHealthLastErrorTimeSensor(readings))
    async_add_entities(entities)


class _SofarCommunicationHealthEntity(
    CoordinatorEntity[SofarDataUpdateCoordinator], SensorEntity
):
    """Base for communication_health entities; available even on a dead link."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: SofarDataUpdateCoordinator, unique_id_suffix: str
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        serial = coordinator.device.serial_number
        self._attr_unique_id = f"{serial}_{unique_id_suffix}"
        self._attr_device_info = build_device_info(coordinator.device)

    @property
    @override
    def available(self) -> bool:
        return True


class SofarCommunicationHealthSensor(_SofarCommunicationHealthEntity):
    """Link-quality summary; one bad cycle in 20 dents this, not any entity."""

    _attr_translation_key = "communication_health"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["good", "degraded", "poor", "unknown"]

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "communication_health")

    @property
    @override
    def native_value(self) -> str:
        rate = self.coordinator.success_rate
        if rate is None:
            return "unknown"
        if rate == 100:
            return "good"
        if rate >= 80:
            return "degraded"
        return "poor"


class SofarCommunicationHealthSuccessRateSensor(_SofarCommunicationHealthEntity):
    """Same rolling window as the health sensor, as a number not a bucket."""

    _attr_translation_key = "communication_health_success_rate"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "communication_health_success_rate")

    @property
    @override
    def native_value(self) -> float | None:
        return self.coordinator.success_rate


class SofarCommunicationHealthLastErrorSensor(_SofarCommunicationHealthEntity):
    """Type + message of the last poll error; not cleared by a later success."""

    _attr_translation_key = "communication_health_last_error"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "communication_health_last_error")

    @property
    @override
    def native_value(self) -> str | None:
        return self.coordinator.last_error


class SofarCommunicationHealthLastErrorTimeSensor(_SofarCommunicationHealthEntity):
    """When the last poll error (see the sibling sensor) happened."""

    _attr_translation_key = "communication_health_last_error_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: SofarDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "communication_health_last_error_time")

    @property
    @override
    def native_value(self) -> datetime | None:
        return self.coordinator.last_error_time


class SofarSensor(SofarEntity, SensorEntity):
    """A read-only value off one of the device's components."""

    entity_description: SofarSensorDescription

    def __init__(
        self,
        runtime_data: SofarRuntimeData,
        description: SofarSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(runtime_data, description.key, description.component)
        self.entity_description = description

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
        super().__init__(runtime_data, description.key, description.component)
        self.entity_description = description
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
class SofarSensorDescription(SensorEntityDescription):
    """A SensorEntityDescription plus which Component the value comes from."""

    # Must subclass (not duck-type): SensorEntity reads fields like
    # suggested_unit_of_measurement straight off entity_description.
    component: str  # attribute name on SofarInverter, e.g. 'grid', 'pv_1_2'


SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = ()
