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
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfVolume,
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

FLOW_ICON = "mdi:shower-head"
GAUGE_ICON = "mdi:gauge"
TDS_ICON = "mdi:water-opacity"

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


@dataclass(kw_only=True)
class DROPSensorEntityDescription(SensorEntityDescription):
    """Describes DROP sensor entity."""

    value_fn: Callable[[DROPDeviceDataUpdateCoordinator], float | int | None]


SENSORS: list[DROPSensorEntityDescription] = [
    DROPSensorEntityDescription(
        key=CURRENT_FLOW_RATE,
        translation_key=CURRENT_FLOW_RATE,
        icon="mdi:shower-head",
        native_unit_of_measurement="gpm",
        suggested_display_precision=1,
        value_fn=lambda device: device.current_flow_rate,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=PEAK_FLOW_RATE,
        translation_key=PEAK_FLOW_RATE,
        icon="mdi:shower-head",
        native_unit_of_measurement="gpm",
        suggested_display_precision=1,
        value_fn=lambda device: device.peak_flow_rate,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=WATER_USED_TODAY,
        translation_key=WATER_USED_TODAY,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=1,
        value_fn=lambda device: device.water_used_today,
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=AVERAGE_WATER_USED,
        translation_key=AVERAGE_WATER_USED,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.average_water_used,
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=CAPACITY_REMAINING,
        translation_key=CAPACITY_REMAINING,
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.GALLONS,
        suggested_display_precision=0,
        value_fn=lambda device: device.capacity_remaining,
        state_class=SensorStateClass.TOTAL,
    ),
    DROPSensorEntityDescription(
        key=CURRENT_SYSTEM_PRESSURE,
        translation_key=CURRENT_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=1,
        value_fn=lambda device: device.current_system_pressure,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=HIGH_SYSTEM_PRESSURE,
        translation_key=HIGH_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda device: device.high_system_pressure,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=LOW_SYSTEM_PRESSURE,
        translation_key=LOW_SYSTEM_PRESSURE,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.PSI,
        suggested_display_precision=0,
        value_fn=lambda device: device.low_system_pressure,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=BATTERY,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda device: device.battery,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        suggested_display_precision=1,
        value_fn=lambda device: device.temperature,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    DROPSensorEntityDescription(
        key=INLET_TDS,
        translation_key=INLET_TDS,
        icon=TDS_ICON,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.inlet_tds,
    ),
    DROPSensorEntityDescription(
        key=OUTLET_TDS,
        translation_key=OUTLET_TDS,
        icon=TDS_ICON,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.outlet_tds,
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_1_LIFE,
        translation_key=CARTRIDGE_1_LIFE,
        icon=GAUGE_ICON,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart1,
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_2_LIFE,
        translation_key=CARTRIDGE_2_LIFE,
        icon=GAUGE_ICON,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart2,
    ),
    DROPSensorEntityDescription(
        key=CARTRIDGE_3_LIFE,
        translation_key=CARTRIDGE_3_LIFE,
        icon=GAUGE_ICON,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.cart3,
    ),
]


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

    coordinator: DROPDeviceDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]
    device_type: str = config_entry.data[CONF_DEVICE_TYPE]
    if device_type == DEV_HUB:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                AVERAGE_WATER_USED,
                BATTERY,
                CURRENT_FLOW_RATE,
                CURRENT_SYSTEM_PRESSURE,
                HIGH_SYSTEM_PRESSURE,
                LOW_SYSTEM_PRESSURE,
                PEAK_FLOW_RATE,
                WATER_USED_TODAY,
            )
        )
    elif device_type == DEV_SOFTENER:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                BATTERY,
                CAPACITY_REMAINING,
                CURRENT_FLOW_RATE,
                CURRENT_SYSTEM_PRESSURE,
            )
        )
    elif device_type == DEV_FILTER:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                BATTERY,
                CURRENT_FLOW_RATE,
                CURRENT_SYSTEM_PRESSURE,
            )
        )
    elif device_type == DEV_LEAK_DETECTOR:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                BATTERY,
                TEMPERATURE,
            )
        )
    elif device_type == DEV_PROTECTION_VALVE:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                BATTERY,
                CURRENT_FLOW_RATE,
                CURRENT_SYSTEM_PRESSURE,
                TEMPERATURE,
            )
        )
    elif device_type == DEV_PUMP_CONTROLLER:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                CURRENT_FLOW_RATE,
                CURRENT_SYSTEM_PRESSURE,
                TEMPERATURE,
            )
        )
    elif device_type == DEV_RO_FILTER:
        async_add_entities(
            DROPSensor(coordinator, sensor)
            for sensor in SENSORS
            if sensor.key
            in (
                CARTRIDGE_1_LIFE,
                CARTRIDGE_2_LIFE,
                CARTRIDGE_3_LIFE,
                INLET_TDS,
                OUTLET_TDS,
            )
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
