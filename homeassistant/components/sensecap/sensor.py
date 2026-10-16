"""Sensor mapping from library device state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

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
class SenseCapSensorDescription[DeviceT: SenseCapDevice](SensorEntityDescription):
    """Select a typed measurement from the device model."""

    device_types: tuple[type[DeviceT], ...]
    value_fn: Callable[[DeviceT], float | None]


DESCRIPTIONS: tuple[SenseCapSensorDescription[Any], ...] = (
    SenseCapSensorDescription[S2101 | S2103](
        key="temperature",
        device_types=(S2101, S2103),
        value_fn=lambda device: device.temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2101 | S2103](
        key="humidity",
        device_types=(S2101, S2103),
        value_fn=lambda device: device.humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2102](
        key="illuminance",
        device_types=(S2102,),
        value_fn=lambda device: device.illuminance,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[S2103](
        key="carbon_dioxide",
        device_types=(S2103,),
        value_fn=lambda device: device.co2,
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=UnitOfRatio.PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription[SenseCapDevice](
        key="battery",
        device_types=(S2101, S2102, S2103),
        value_fn=lambda device: (
            battery_level
            if (battery_level := device.battery_level) is not None
            else device.battery_percentage
        ),
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
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
            if isinstance(coordinator.data, description.device_types)
        )

    entry.async_on_unload(entry.runtime_data.subscribe_coordinator_added(added))


class SenseCapSensor(LoRaWANEntity[SenseCapDevice], SensorEntity):
    """Home Assistant entity representing a SenseCAP device datapoint."""

    coordinator: SenseCapCoordinator
    entity_description: SenseCapSensorDescription[Any]

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last observed measurement."""
        return self.entity_description.value_fn(self.device)
