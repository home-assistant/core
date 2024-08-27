"""Support for Iskra."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from pyiskra import CounterType
from pyiskra.devices import Device

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    POWER_VOLT_AMPERE_REACTIVE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
from .entity import IskraDevice

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=60)


_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IskraRequiredKeysMixin:
    """Mixin for required keys."""

    value_func: Callable[[Device], float | None]


@dataclass(frozen=True)
class IskraSensorEntityDescription(SensorEntityDescription, IskraRequiredKeysMixin):
    """Describes Iskra sensor entity."""


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
        native_unit_of_measurement=POWER_VOLT_AMPERE_REACTIVE,
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
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Iskra sensors based on config_entry."""

    # Device that uses the config entry.
    root_device = entry.runtime_data.get("root_device")
    coordinators = entry.runtime_data.get("coordinators")

    # Add sensors for each device.
    for coordinator in coordinators:
        device = coordinator.device
        await coordinator.async_config_entry_first_refresh()
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

        entities = [
            IskraSensor(coordinator, root_device, entry, description)
            for description in SENSOR_TYPES
            if description.key in sensors
        ]

        # Add resettable and non-resettable counters.
        if device.supports_counters:
            # Add Non-resettable counters.
            for index, counter in enumerate(device.counters.non_resettable):

                def non_resettable_value_func(device, counter_index):
                    return lambda device: round(
                        device.counters.non_resettable[counter_index].value, 2
                    )

                sensor_entity_description = IskraSensorEntityDescription(
                    key=f"nresettable_counter{index+1}",
                    translation_key=f"nresettable_counter{index+1}",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    # If counter is for active energy mark it as energy sensor otherwise dont set device clas.
                    # This is due to the fact that HA does not support reactive energy sensors.
                    device_class=(
                        SensorDeviceClass.ENERGY
                        if counter.counter_type
                        in [CounterType.ACTIVE_IMPORT, CounterType.ACTIVE_EXPORT]
                        else None
                    ),
                    # Use HA energy unit for active energy counters otherwise use units from API.
                    native_unit_of_measurement=(
                        UnitOfEnergy.WATT_HOUR
                        if counter.counter_type
                        in [CounterType.ACTIVE_IMPORT, CounterType.ACTIVE_EXPORT]
                        else counter.units
                    ),
                    value_func=non_resettable_value_func(device, index),
                )
                entities.append(
                    IskraSensor(
                        coordinator, root_device, entry, sensor_entity_description
                    )
                )

            # Add resettable counters.
            for index, counter in enumerate(device.counters.resettable):

                def resettable_value_func(device, counter_index):
                    return lambda device: round(
                        device.counters.resettable[counter_index].value, 2
                    )

                sensor_entity_description = IskraSensorEntityDescription(
                    key=f"resettable_counter{index+1}",
                    translation_key=f"resettable_counter{index+1}",
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    # If counter is for active energy mark it as energy sensor otherwise dont set device clas.
                    # This is due to the fact that HA does not support reactive energy sensors.
                    device_class=(
                        SensorDeviceClass.ENERGY
                        if counter.counter_type
                        in [CounterType.ACTIVE_IMPORT, CounterType.ACTIVE_EXPORT]
                        else None
                    ),
                    # Use HA energy unit for active energy counters otherwise use units from API.
                    native_unit_of_measurement=(
                        UnitOfEnergy.WATT_HOUR
                        if counter.counter_type
                        in [CounterType.ACTIVE_IMPORT, CounterType.ACTIVE_EXPORT]
                        else counter.units
                    ),
                    value_func=resettable_value_func(device, index),
                )

                entities.append(
                    IskraSensor(
                        coordinator, root_device, entry, sensor_entity_description
                    )
                )

        async_add_entities(entities)


class IskraSensor(IskraDevice, CoordinatorEntity, SensorEntity):
    """Representation of a Sensor."""

    _attr_has_entity_name = True
    entity_description: IskraSensorEntityDescription
    coordinator: IskraDataUpdateCoordinator

    def __init__(
        self,
        coordinator: IskraDataUpdateCoordinator,
        gateway,
        config_entry,
        description: IskraSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""

        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device.serial}_{description.key}"
        self._unique_id = self._attr_unique_id
        IskraDevice.__init__(self, coordinator.device, gateway, config_entry)
        CoordinatorEntity.__init__(self, coordinator, self._unique_id)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.coordinator.device)
