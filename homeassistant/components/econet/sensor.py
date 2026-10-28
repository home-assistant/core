"""Support for Rheem EcoNet water heaters."""

from typing import override

from pyeconet.equipment import Equipment, EquipmentType

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfEnergy,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import EconetConfigEntry
from .entity import EcoNetEntity

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="tank_health",
        translation_key="tank_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="tank_hot_water_availability",
        translation_key="available_hot_water",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="compressor_health",
        translation_key="compressor_health",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="override_status",
        translation_key="override_status",
    ),
    SensorEntityDescription(
        key="todays_water_usage",
        translation_key="water_usage_today",
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="todays_energy_usage",
        translation_key="power_usage_today",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="alert_count",
        translation_key="alert_count",
    ),
    SensorEntityDescription(
        key="wifi_signal",
        translation_key="wifi_signal",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="running_state",
        translation_key="running_state",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EconetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up EcoNet sensor based on a config entry."""

    data = entry.runtime_data
    equipment = data[EquipmentType.WATER_HEATER].copy()
    equipment.extend(data[EquipmentType.THERMOSTAT].copy())

    sensors = [
        EcoNetSensor(_equip, description)
        for _equip in equipment
        for description in SENSOR_TYPES
        if getattr(_equip, description.key, False) is not False
    ]

    async_add_entities(sensors)


class EcoNetSensor(EcoNetEntity, SensorEntity):
    """Define a Econet sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        econet_device: Equipment,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(econet_device)
        self.entity_description = description
        # Translation keys are also legacy unique-ID suffixes and must stay stable.
        self._attr_unique_id = f"{econet_device.device_id}_{econet_device.device_name}_{description.translation_key}"

    @property
    @override
    def native_value(self):
        """Return sensors state."""
        value = getattr(self._econet, self.entity_description.key)
        if value is None:
            return None
        if (
            self.entity_description.key == "todays_energy_usage"
            and self._econet.energy_type == "KBTU"
        ):
            value = value * 0.2930710702  # Convert kBtu to kWh
        if isinstance(value, float):
            value = round(value, 2)
        return value
