"""Sensor entities for the Solyx Energy Nymo integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import callback

from .coordinator import SolyxEnergyConfigEntry, SolyxEnergyData
from .entity import SolyxNymoEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SolyxSensorEntityDescription(SensorEntityDescription):
    """Describes Solyx Energy sensor entity."""

    value_fn: Callable[[SolyxEnergyData], float | None]


SENSOR_DESCRIPTIONS: tuple[SolyxSensorEntityDescription, ...] = (
    SolyxSensorEntityDescription(
        key="boiler_current",
        translation_key="boiler_current",
        value_fn=lambda data: data.boiler_current,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    SolyxSensorEntityDescription(
        key="boiler_power",
        translation_key="boiler_power",
        value_fn=lambda data: data.boiler_power,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SolyxSensorEntityDescription(
        key="boiler_voltage",
        translation_key="boiler_voltage",
        value_fn=lambda data: data.boiler_voltage,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    SolyxSensorEntityDescription(
        key="days_since_maximum_temperature",
        translation_key="days_since_maximum_temperature",
        value_fn=lambda data: data.days_since_maximum_temperature,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    SolyxSensorEntityDescription(
        key="grid_power",
        translation_key="grid_power",
        value_fn=lambda data: data.grid_power,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
    SolyxSensorEntityDescription(
        key="legionella_days",
        translation_key="legionella_days",
        value_fn=lambda data: data.legionella_days,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTime.DAYS,
    ),
    SolyxSensorEntityDescription(
        key="saved_this_month",
        translation_key="saved_this_month",
        value_fn=lambda data: data.saved_this_month,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SolyxSensorEntityDescription(
        key="saved_this_week",
        translation_key="saved_this_week",
        value_fn=lambda data: data.saved_this_week,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    SolyxSensorEntityDescription(
        key="saved_today",
        translation_key="saved_today",
        value_fn=lambda data: data.saved_today,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
)


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: SolyxEnergyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Solyx Energy sensors from a config entry."""
    coordinator = entry.runtime_data
    known_devices: set[str] = set()

    @callback
    def _add_new_devices() -> None:
        new_devices = set(coordinator.data) - known_devices
        if not new_devices:
            return

        known_devices.update(new_devices)
        async_add_entities(
            SolyxSensorEntity(coordinator, description, device_id)
            for device_id in sorted(new_devices)
            for description in SENSOR_DESCRIPTIONS
        )

    _add_new_devices()
    entry.async_on_unload(coordinator.async_add_listener(_add_new_devices))


class SolyxSensorEntity(SolyxNymoEntity, SensorEntity):
    """A single Solyx Energy sensor entity."""

    entity_description: SolyxSensorEntityDescription

    @property
    @override
    def native_value(self) -> float | None:
        """Retrieve the parsed (native) value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data[self.device_id])
