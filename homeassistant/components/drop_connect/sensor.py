"""Support for DROP sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_TYPE,
    DEV_FILTER,
    DEV_HUB,
    DEV_LEAK_DETECTOR,
    DEV_PROTECTION_VALVE,
    DEV_PUMP_CONTROLLER,
    DEV_RO_FILTER,
    DEV_SOFTENER,
    DOMAIN,
)
from .coordinator import DROPDeviceDataUpdateCoordinator
from .entity import DROPEntity

_LOGGER = logging.getLogger(__name__)


# Sensor type constants
CURRENT_FLOW_RATE = "current_flow_rate"
PEAK_FLOW_RATE = "peak_flow_rate"
WATER_USED_TODAY = "water_used_today"
AVERAGE_WATER_USED = "average_water_used"
CAPACITY_REMAINING = "capacity_remaining"
CURRENT_SYSTEM_PRESSURE = "current_system_pressure"
HIGH_SYSTEM_PRESSURE = "high_system_pressure"
LOW_SYSTEM_PRESSURE = "low_system_pressure"
BATTERY = "battery"
TEMPERATURE = "temperature"
INLET_TDS = "inlet_tds"
OUTLET_TDS = "outlet_tds"
CARTRIDGE_1_LIFE = "cart1"
CARTRIDGE_2_LIFE = "cart2"
CARTRIDGE_3_LIFE = "cart3"


@dataclass(kw_only=True, frozen=True)
class DROPSensorEntityDescription(SensorEntityDescription):
    """Describes DROP sensor entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], float | int | None]


SENSORS: list[DROPSensorEntityDescription] = [
    DROPSensorEntityDescription(
        key=CURRENT_FLOW_RATE,
        translation_key=CURRENT_FLOW_RATE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_display_precision=1,
        value_fn=lambda device: device.drop_api.current_flow_rate(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=PEAK_FLOW_RATE,
        translation_key=PEAK_FLOW_RATE,
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.GALLONS_PER_MINUTE,
        suggested_display_precision=1,
        value_fn=lambda device: device.drop_api.peak_flow_rate(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=WATER_USED_TODAY,
        translation_key=WATER_USED_TODAY,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=lambda device: device.drop_api.water_used_today(),
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=AVERAGE_WATER_USED,
        translation_key=AVERAGE_WATER_USED,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.average_water_used(),
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=CAPACITY_REMAINING,
        translation_key=CAPACITY_REMAINING,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.capacity_remaining(),
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=CURRENT_SYSTEM_PRESSURE,
        translation_key=CURRENT_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=1,
        value_fn=lambda device: device.drop_api.current_system_pressure(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=HIGH_SYSTEM_PRESSURE,
        translation_key=HIGH_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.high_system_pressure(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=LOW_SYSTEM_PRESSURE,
        translation_key=LOW_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.low_system_pressure(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=BATTERY,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.battery(),
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    DROPSensorEntityDescription(
        key=TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        suggested_display_precision=1,
        value_fn=lambda device: device.drop_api.temperature(),
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=INLET_TDS,
        translation_key=INLET_TDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.inlet_tds(),
    ),
    DROPSensorEntityDescription(
        key=OUTLET_TDS,
        translation_key=OUTLET_TDS,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.outlet_tds(),
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_1_LIFE,
        translation_key=CARTRIDGE_1_LIFE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.cart1(),
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_2_LIFE,
        translation_key=CARTRIDGE_2_LIFE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.cart2(),
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_3_LIFE,
        translation_key=CARTRIDGE_3_LIFE,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=0,
        value_fn=lambda device: device.drop_api.cart3(),
    ),
]

# Defines which sensors are used by each device type
DEVICE_SENSORS: dict[str, list[str]] = {
    DEV_HUB: [
        AVERAGE_WATER_USED,
        BATTERY,
        CURRENT_FLOW_RATE,
        CURRENT_SYSTEM_PRESSURE,
        HIGH_SYSTEM_PRESSURE,
        LOW_SYSTEM_PRESSURE,
        PEAK_FLOW_RATE,
        WATER_USED_TODAY,
    ],
    DEV_SOFTENER: [
        BATTERY,
        CAPACITY_REMAINING,
        CURRENT_FLOW_RATE,
        CURRENT_SYSTEM_PRESSURE,
    ],
    DEV_FILTER: [BATTERY, CURRENT_FLOW_RATE, CURRENT_SYSTEM_PRESSURE],
    DEV_LEAK_DETECTOR: [BATTERY, TEMPERATURE],
    DEV_PROTECTION_VALVE: [
        BATTERY,
        CURRENT_FLOW_RATE,
        CURRENT_SYSTEM_PRESSURE,
        TEMPERATURE,
    ],
    DEV_PUMP_CONTROLLER: [CURRENT_FLOW_RATE, CURRENT_SYSTEM_PRESSURE, TEMPERATURE],
    DEV_RO_FILTER: [
        CARTRIDGE_1_LIFE,
        CARTRIDGE_2_LIFE,
        CARTRIDGE_3_LIFE,
        INLET_TDS,
        OUTLET_TDS,
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DROP sensors from config entry."""
    _LOGGER.debug(
        "Set up sensor for device type %s with entry_id is %s",
        config_entry.data[CONF_DEVICE_TYPE],
        config_entry.entry_id,
    )

    if config_entry.data[CONF_DEVICE_TYPE] in DEVICE_SENSORS:
        async_add_entities(
            DROPSensor(hass.data[DOMAIN][config_entry.entry_id], sensor)
            for sensor in SENSORS
            if sensor.key in DEVICE_SENSORS[config_entry.data[CONF_DEVICE_TYPE]]
        )


class DROPSensor(DROPEntity, SensorEntity):
    """Representation of a DROP sensor."""

    entity_description: DROPSensorEntityDescription

    def __init__(
        self,
        coordinator: DROPDeviceDataUpdateCoordinator,
        entity_description: DROPSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entity_description.key, coordinator)
        self.entity_description = entity_description

    @property
    def native_value(self) -> float | int | None:
        """Return the value reported by the sensor."""
        return self.entity_description.value_fn(self.coordinator)
