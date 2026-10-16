"""Sensor mapping from library device state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from sensecap_lorawan import S2101, S2102, S2103, SenseCapDevice

from homeassistant.components.lorawan import LoRaWANEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    LIGHT_LUX,
    PERCENTAGE,
    EntityCategory,
    UnitOfRatio,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SenseCapConfigEntry
from .coordinator import SenseCapCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SenseCapSensorDescription(SensorEntityDescription):
    """Select a typed measurement from the device model."""

    device_type: type[S2101 | S2102 | S2103]
    value_fn: Callable[[SenseCapDevice], float | None]


def _battery_level(device: SenseCapDevice) -> float | None:
    """Use LoRaWAN status with SenseCAP uplink battery data as a fallback."""
    if (battery_level := device.battery_level) is not None:
        return battery_level
    return device.battery_percentage


DESCRIPTIONS = (
    *(
        SenseCapSensorDescription(
            key="temperature",
            device_type=device_type,
            value_fn=lambda device: cast(S2101 | S2103, device).temperature,
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for device_type in (S2101, S2103)
    ),
    *(
        SenseCapSensorDescription(
            key="humidity",
            device_type=device_type,
            value_fn=lambda device: cast(S2101 | S2103, device).humidity,
            device_class=SensorDeviceClass.HUMIDITY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
        )
        for device_type in (S2101, S2103)
    ),
    SenseCapSensorDescription(
        key="illuminance",
        device_type=S2102,
        value_fn=lambda device: cast(S2102, device).illuminance,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription(
        key="carbon_dioxide",
        device_type=S2103,
        value_fn=lambda device: cast(S2103, device).co2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    *(
        SenseCapSensorDescription(
            key="battery",
            device_type=device_type,
            value_fn=_battery_level,
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        for device_type in (S2101, S2102, S2103)
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SenseCapConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for existing and newly discovered devices."""

    @callback
    def added(coordinator: SenseCapCoordinator) -> None:
        async_add_entities(
            SenseCapSensor(coordinator, description)
            for description in DESCRIPTIONS
            if isinstance(coordinator.data, description.device_type)
        )

    entry.async_on_unload(entry.runtime_data.subscribe_coordinator_added(added))


class SenseCapSensor(LoRaWANEntity[SenseCapDevice], SensorEntity):
    """Home Assistant entity representing a SenseCAP device datapoint."""

    coordinator: SenseCapCoordinator
    entity_description: SenseCapSensorDescription

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last observed measurement."""
        return self.entity_description.value_fn(self.device)
