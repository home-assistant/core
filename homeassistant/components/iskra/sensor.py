"""Support for Iskra."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pyiskra.devices import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IskraConfigEntry
from .const import (
    ATTR_FREQUENCY,
    ATTR_PHASE1_CURRENT,
    ATTR_PHASE1_POWER,
    ATTR_PHASE1_VOLTAGE,
    ATTR_PHASE2_CURRENT,
    ATTR_PHASE2_POWER,
    ATTR_PHASE2_VOLTAGE,
    ATTR_PHASE3_CURRENT,
    ATTR_PHASE3_POWER,
    ATTR_PHASE3_VOLTAGE,
    ATTR_TOTAL_ACTIVE_POWER,
    ATTR_TOTAL_APPARENT_POWER,
    ATTR_TOTAL_REACTIVE_POWER,
)
from .coordinator import IskraDataUpdateCoordinator
from .entity import IskraEntity


@dataclass(frozen=True, kw_only=True)
class IskraSensorEntityDescription(SensorEntityDescription):
    """Describes Iskra sensor entity."""

    value_func: Callable[[Device], float | None]


SENSOR_TYPES: tuple[IskraSensorEntityDescription, ...] = (
    # Power
    IskraSensorEntityDescription(
        key=ATTR_TOTAL_ACTIVE_POWER,
        translation_key="total_active_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.measurements.total.active_power.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_TOTAL_REACTIVE_POWER,
        translation_key="total_reactive_power",
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        value_func=lambda device: device.measurements.total.reactive_power.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_TOTAL_APPARENT_POWER,
        translation_key="total_apparent_power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        value_func=lambda device: device.measurements.total.apparent_power.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE1_POWER,
        translation_key="phase1_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.measurements.phases[0].active_power.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE2_POWER,
        translation_key="phase2_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.measurements.phases[1].active_power.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE3_POWER,
        translation_key="phase3_power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.measurements.phases[2].active_power.value,
    ),
    # Voltage
    IskraSensorEntityDescription(
        key=ATTR_PHASE1_VOLTAGE,
        translation_key="phase1_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=lambda device: device.measurements.phases[0].voltage.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE2_VOLTAGE,
        translation_key="phase2_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=lambda device: device.measurements.phases[1].voltage.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE3_VOLTAGE,
        translation_key="phase3_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=lambda device: device.measurements.phases[2].voltage.value,
    ),
    # Current
    IskraSensorEntityDescription(
        key=ATTR_PHASE1_CURRENT,
        translation_key="phase1_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=lambda device: device.measurements.phases[0].current.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE2_CURRENT,
        translation_key="phase2_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=lambda device: device.measurements.phases[1].current.value,
    ),
    IskraSensorEntityDescription(
        key=ATTR_PHASE3_CURRENT,
        translation_key="phase3_current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=lambda device: device.measurements.phases[2].current.value,
    ),
    # Frequency
    IskraSensorEntityDescription(
        key=ATTR_FREQUENCY,
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        value_func=lambda device: device.measurements.frequency.value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IskraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Iskra sensors based on config_entry."""

    # Device that uses the config entry.
    coordinators = entry.runtime_data

    entities: list[IskraSensor] = []

    # Add sensors for each device.
    for coordinator in coordinators:
        device = coordinator.device
        sensors = []

        # Add measurement sensors.
        if device.supports_measurements:
            sensors.append(ATTR_FREQUENCY)
            sensors.append(ATTR_TOTAL_APPARENT_POWER)
            sensors.append(ATTR_TOTAL_ACTIVE_POWER)
            sensors.append(ATTR_TOTAL_REACTIVE_POWER)
            if device.phases >= 1:
                sensors.append(ATTR_PHASE1_VOLTAGE)
                sensors.append(ATTR_PHASE1_POWER)
                sensors.append(ATTR_PHASE1_CURRENT)
            if device.phases >= 2:
                sensors.append(ATTR_PHASE2_VOLTAGE)
                sensors.append(ATTR_PHASE2_POWER)
                sensors.append(ATTR_PHASE2_CURRENT)
            if device.phases >= 3:
                sensors.append(ATTR_PHASE3_VOLTAGE)
                sensors.append(ATTR_PHASE3_POWER)
                sensors.append(ATTR_PHASE3_CURRENT)

        entities.extend(
            IskraSensor(coordinator, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        )

    async_add_entities(entities)


class IskraSensor(IskraEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: IskraSensorEntityDescription

    def __init__(
        self,
        coordinator: IskraDataUpdateCoordinator,
        description: IskraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.serial}_{description.key}"

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.device)
