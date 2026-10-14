"""Sensor mapping from library device state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast, override

from sensecap_lorawan import S2101, S2102, SenseCapDevice

from homeassistant.components.lorawan import LoRaWANEntity
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import LIGHT_LUX, PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SenseCapConfigEntry
from .coordinator import SenseCapCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SenseCapSensorDescription(SensorEntityDescription):
    """Select a typed measurement from the device model."""

    device_type: type[S2101 | S2102]
    value_fn: Callable[[SenseCapDevice], float | None]


DESCRIPTIONS = (
    SenseCapSensorDescription(
        key="temperature",
        device_type=S2101,
        value_fn=lambda device: cast(S2101, device).temperature,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription(
        key="humidity",
        device_type=S2101,
        value_fn=lambda device: cast(S2101, device).humidity,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SenseCapSensorDescription(
        key="illuminance",
        device_type=S2102,
        value_fn=lambda device: cast(S2102, device).illuminance,
        device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX,
        state_class=SensorStateClass.MEASUREMENT,
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
    """Read typed state; decoding and event interpretation belong to the library."""

    coordinator: SenseCapCoordinator
    entity_description: SenseCapSensorDescription

    def __init__(
        self, coordinator: SenseCapCoordinator, description: SenseCapSensorDescription
    ) -> None:
        """Bind one measurement to its model."""
        super().__init__(coordinator)
        self.entity_description = description
        descriptor = self.device.descriptor
        identity = f"{descriptor.network_id}:{descriptor.dev_eui}"
        self._attr_unique_id = f"{identity}:{description.key}"

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return self.coordinator.device_info

    @property
    @override
    def native_value(self) -> float | None:
        """Return the last observed measurement."""
        return self.entity_description.value_fn(self.device)
