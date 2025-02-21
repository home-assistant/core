"""Support for meross_scan sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from meross_ha.controller.electricity import ElectricityXMix

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CHANNEL_DISPLAY_NAME, SENSOR_EM
from .coordinator import MerossDataUpdateCoordinator
from .entity import MerossEntity


@dataclass(frozen=True)
class MerossSensorEntityDescription(SensorEntityDescription):
    """Describes Meross sensor entity."""

    subkey: str | None = None
    fn: Callable[[float], float] | None = None


DEVICETYPE_SENSOR: dict[str, str] = {
    "em06": SENSOR_EM,
    "em16": SENSOR_EM,
}

SENSORS: dict[str, tuple[MerossSensorEntityDescription, ...]] = {
    SENSOR_EM: (
        MerossSensorEntityDescription(
            key="power",
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            subkey="power",
            fn=lambda x: x / 1000.0,
        ),
        MerossSensorEntityDescription(
            key="voltage",
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        MerossSensorEntityDescription(
            key="current",
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            subkey="current",
        ),
        MerossSensorEntityDescription(
            key="factor",
            translation_key="power_factor",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            subkey="factor",
        ),
        MerossSensorEntityDescription(
            key="energy",
            translation_key="this_month_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: max(0, x),
        ),
        MerossSensorEntityDescription(
            key="energy_returned",
            translation_key="this_month_energy_returned",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: abs(x) if x < 0 else 0,
        ),
    ),
    "em16": (
        MerossSensorEntityDescription(
            key="power",
            translation_key="power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            suggested_display_precision=2,
            subkey="power",
            fn=lambda x: x / 1000.0,
        ),
        MerossSensorEntityDescription(
            key="voltage",
            translation_key="voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.MILLIVOLT,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricPotential.VOLT,
            subkey="voltage",
        ),
        MerossSensorEntityDescription(
            key="current",
            translation_key="current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
            suggested_display_precision=2,
            suggested_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
            subkey="current",
        ),
        MerossSensorEntityDescription(
            key="factor",
            translation_key="power_factor",
            device_class=SensorDeviceClass.POWER_FACTOR,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=2,
            subkey="factor",
        ),
        MerossSensorEntityDescription(
            key="energy",
            translation_key="this_month_energy",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: max(0, x),
        ),
        MerossSensorEntityDescription(
            key="energy_returned",
            translation_key="this_month_energy_returned",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
            suggested_display_precision=2,
            subkey="mConsume",
            fn=lambda x: abs(x) if x < 0 else 0,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Meross device from a config entry."""
    coordinator = config_entry.runtime_data
    device = coordinator.device
    if not isinstance(device, ElectricityXMix):
        return

    sensor_type = DEVICETYPE_SENSOR.get(device.device_type, "")
    descriptions: tuple[MerossSensorEntityDescription, ...] = SENSORS.get(
        sensor_type, ()
    )
    async_add_entities(
        MerossSensor(
            coordinator=coordinator,
            channel=channel,
            description=description,
        )
        for channel in device.channels
        for description in descriptions
    )


class MerossSensor(MerossEntity, SensorEntity):
    """Meross Sensor Device."""

    entity_description: MerossSensorEntityDescription

    def __init__(
        self,
        coordinator: MerossDataUpdateCoordinator,
        channel: int,
        description: MerossSensorEntityDescription,
    ) -> None:
        """Init Meross sensor."""
        super().__init__(coordinator, channel)
        self.entity_description = description
        self._attr_unique_id = f"{super().unique_id}{description.key}"
        device_type = coordinator.device.device_type
        channel_name = CHANNEL_DISPLAY_NAME[device_type][channel]
        self._attr_translation_placeholders = {"channel_name": channel_name}

    @property
    def native_value(self) -> StateType:
        """Return the native value."""
        value = self.coordinator.device.get_value(
            self.channel, self.entity_description.subkey
        )
        if value is None:
            return None
        if self.entity_description.fn:
            return self.entity_description.fn(value)
        return value
