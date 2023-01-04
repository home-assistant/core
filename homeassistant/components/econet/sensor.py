"""Support for Rheem EcoNet water heaters."""
from __future__ import annotations

from dataclasses import dataclass

from pyeconet.equipment import EquipmentType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import EcoNetEntity
from .const import DOMAIN, EQUIPMENT


@dataclass
class EcoNetSensorEntityDescription(SensorEntityDescription):
    """Represent the econet sensor entity description."""


SENSOR_TYPES: tuple[EcoNetSensorEntityDescription, ...] = (
    EcoNetSensorEntityDescription(
        key="tank_health",
        name="tank_health",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoNetSensorEntityDescription(
        key="tank_hot_water_availability",
        name="available_hot_water",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoNetSensorEntityDescription(
        key="compressor_health",
        name="compressor_health",
        native_unit_of_measurement=PERCENTAGE,
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoNetSensorEntityDescription(
        key="override_status",
        name="override_status",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
    ),
    EcoNetSensorEntityDescription(
        key="todays_water_usage",
        name="water_usage_today",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoNetSensorEntityDescription(
        key="todays_energy_usage",
        name="power_usage_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcoNetSensorEntityDescription(
        key="alert_count",
        name="alert_count",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
    ),
    EcoNetSensorEntityDescription(
        key="wifi_signal",
        name="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    EcoNetSensorEntityDescription(
        key="running_state",
        name="running_state",
        native_unit_of_measurement=None,
        device_class=None,
        state_class=None,
    ),
)


ENERGY_KILO_BRITISH_THERMAL_UNIT = "kBtu"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up EcoNet sensor based on a config entry."""

    data = hass.data[DOMAIN][EQUIPMENT][entry.entry_id]
    equipment = data[EquipmentType.WATER_HEATER].copy()
    equipment.extend(data[EquipmentType.THERMOSTAT].copy())

    sensors = []

    sensors = [
        EcoNetSensor(_equip, description.name, description)
        for _equip in equipment
        for description in SENSOR_TYPES
        if getattr(_equip, description.key, False) is not False
    ]

    async_add_entities(sensors)


class EcoNetSensor(EcoNetEntity, SensorEntity):
    """Define a Econet sensor."""

    entity_description: EcoNetSensorEntityDescription

    def __init__(
        self,
        econet_device,
        device_name,
        description: EcoNetSensorEntityDescription,
    ):
        """Initialize."""
        super().__init__(econet_device)
        self.entity_description = description
        self._econet = econet_device
        self._device_name = device_name

    @property
    def native_value(self):
        """Return sensors state."""
        value = getattr(self._econet, self.entity_description.key)
        if self._device_name == "power_usage_today":
            if self._econet.energy_type == ENERGY_KILO_BRITISH_THERMAL_UNIT.upper():
                value = value * 0.2930710702  # Convert kBtu to kWh
        if isinstance(value, float):
            value = round(value, 2)
        return value

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.entity_description.native_unit_of_measurement

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return f"{self._econet.device_name}_{self._device_name}"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return (
            f"{self._econet.device_id}_{self._econet.device_name}_{self._device_name}"
        )
