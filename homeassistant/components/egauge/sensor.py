"""Sensor platform for eGauge energy monitors."""

from __future__ import annotations

from egauge_async.json.models import RegisterInfo, RegisterType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfEnergy, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import EgaugeDataCoordinator
from .entity import EgaugeEntity
from .models import EgaugeConfigEntry


class EgaugePowerSensor(EgaugeEntity, SensorEntity):
    """Sensor for instantaneous power measurement."""

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self,
        coordinator: EgaugeDataCoordinator,
        register_name: str,
        register_info: RegisterInfo,
    ) -> None:
        """Initialize the power sensor."""
        super().__init__(coordinator, register_name, register_info)
        self._attr_unique_id = f"{coordinator.serial_number}_{register_name}_power"
        self._attr_name = register_name

    @property
    def native_value(self) -> float | None:
        """Return the current power value."""
        return self.coordinator.data.measurements.get(self._register_name)


class EgaugeEnergySensor(EgaugeEntity, SensorEntity):
    """Sensor for cumulative energy (for Energy Dashboard)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR

    def __init__(
        self,
        coordinator: EgaugeDataCoordinator,
        register_name: str,
        register_info: RegisterInfo,
    ) -> None:
        """Initialize the energy sensor."""
        super().__init__(coordinator, register_name, register_info)
        self._attr_unique_id = f"{coordinator.serial_number}_{register_name}_energy"
        self._attr_name = f"{register_name} energy"

    @property
    def native_value(self) -> float | None:
        """Return energy in kWh."""
        watt_seconds = self.coordinator.data.counters.get(self._register_name)
        if watt_seconds is None:
            return None
        # Convert Ws → kWh
        return watt_seconds / 3_600_000

    @property
    def last_reset(self) -> None:
        """Counter never resets (lifetime total)."""
        return None


# To add support for additional sensor types:
# 1. Create sensor class (e.g., EgaugeTemperatureSensor)
# 2. Add to SENSOR_TYPES mapping below
# 3. If cumulative tracking needed, add to CUMULATIVE_TYPES
# No coordinator, model, or test fixture changes required!

# Mapping of supported register types to sensor classes (extensible!)
SENSOR_TYPES: dict[RegisterType, type[SensorEntity]] = {
    RegisterType.POWER: EgaugePowerSensor,
}

# Register types that need cumulative (energy) sensors
CUMULATIVE_TYPES = {RegisterType.POWER}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EgaugeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up eGauge sensor platform."""
    coordinator = entry.runtime_data
    sensors: list[SensorEntity] = []

    for name, info in coordinator.data.register_info.items():
        # Skip unsupported types gracefully
        if info.type not in SENSOR_TYPES:
            continue

        # Create instantaneous sensor
        sensor_class = SENSOR_TYPES[info.type]
        sensors.append(sensor_class(coordinator, name, info))  # type: ignore[call-arg]

        # Create cumulative sensor if applicable
        if info.type in CUMULATIVE_TYPES:
            sensors.append(EgaugeEnergySensor(coordinator, name, info))

    async_add_entities(sensors)
