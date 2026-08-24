"""One entity per served row; each is available independently."""

from dataclasses import dataclass
from datetime import date
from enum import IntEnum
from typing import cast, override

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SofarConfigEntry
from .entity import SofarEntity, SofarEntityDescription


def _enum_label(member_name: str) -> str:
    """Format an IntEnum member name to match an ENUM sensor option."""
    return " ".join(word.capitalize() for word in member_name.split("_"))


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
    async_add_entities(entities)


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

    @property
    @override
    def available(self) -> bool:
        # Unconditional: long-term stats survive a link drop or offline night.
        return True

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_data := await self.async_get_last_sensor_data()) is None:
            return
        if last_data.native_value is None:
            return
        try:
            val = float(str(last_data.native_value))
        except ValueError, TypeError:
            return
        self._attr_native_value = val
        if self.entity_description.state_class is SensorStateClass.TOTAL_INCREASING:
            component = getattr(
                self.coordinator.device, self.entity_description.component
            )
            component.seed_high_water(self.entity_description.key, val)

    @property
    @override
    def native_value(self) -> int | float | None:
        component = getattr(self.coordinator.device, self.entity_description.component)
        if self.entity_description.state_class is SensorStateClass.TOTAL_INCREASING:
            value = component.corrected(self.entity_description.key)
        else:
            value = getattr(component, self.entity_description.key)
        if isinstance(value, (int, float)):
            self._attr_native_value = value
        return cast(int | float | None, self._attr_native_value)


@dataclass(frozen=True, kw_only=True)
class SofarSensorDescription(SensorEntityDescription, SofarEntityDescription):
    """A SensorEntityDescription bound to which Component the value comes from."""


SENSOR_DESCRIPTIONS: tuple[SofarSensorDescription, ...] = (
    SofarSensorDescription(
        key="pv_power_1",
        component="pv_1_2",
        translation_key="pv_power_1",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SofarSensorDescription(
        key="pv_power_2",
        component="pv_1_2",
        translation_key="pv_power_2",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    SofarSensorDescription(
        key="pv_power_total",
        component="pv_1_2",
        translation_key="pv_power_total",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SofarSensorDescription(
        key="solar_generation_total",
        component="energy",
        translation_key="solar_generation_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=2,
    ),
)
