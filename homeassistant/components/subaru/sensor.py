"""Support for Subaru sensors."""
import logging

import subarulink.const as sc

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import DistanceConverter, VolumeConverter
from homeassistant.util.unit_system import (
    IMPERIAL_SYSTEM,
    LENGTH_UNITS,
    PRESSURE_UNITS,
    TEMPERATURE_UNITS,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import IMPERIAL_SYSTEM, LENGTH_UNITS, PRESSURE_UNITS

from . import get_device_info
from .const import (
    API_GEN_2,
    DOMAIN,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_SAFETY_SERVICE,
    VEHICLE_NAME,
    VEHICLE_STATUS,
    VEHICLE_VIN,
)

_LOGGER = logging.getLogger(__name__)

L_PER_GAL = VolumeConverter.convert(1, VOLUME_GALLONS, VOLUME_LITERS)
KM_PER_MI = DistanceConverter.convert(1, LENGTH_MILES, LENGTH_KILOMETERS)

# Fuel Economy Constants
FUEL_CONSUMPTION_L_PER_100KM = "L/100km"
FUEL_CONSUMPTION_MPG = "mi/gal"
FUEL_CONSUMPTION_UNITS = [FUEL_CONSUMPTION_L_PER_100KM, FUEL_CONSUMPTION_MPG]

SENSOR_KEY_TO_SUFFIX = {
    sc.ODOMETER: "Odometer",
    sc.AVG_FUEL_CONSUMPTION: "Avg Fuel Consumption",
    sc.DIST_TO_EMPTY: "Range",
    sc.TIRE_PRESSURE_FL: "Tire Pressure FL",
    sc.TIRE_PRESSURE_FR: "Tire Pressure FR",
    sc.TIRE_PRESSURE_RL: "Tire Pressure RL",
    sc.TIRE_PRESSURE_RR: "Tire Pressure RR",
    sc.EXTERNAL_TEMP: "External Temp",
    sc.BATTERY_VOLTAGE: "12V Battery Voltage",
    sc.EV_DISTANCE_TO_EMPTY: "EV Range",
    sc.EV_STATE_OF_CHARGE_PERCENT: "EV Battery Level",
    sc.EV_TIME_TO_FULLY_CHARGED_UTC: "EV Time to Full Charge",
}

# Sensor available to "Subaru Safety Plus" subscribers with Gen1 or Gen2 vehicles
SAFETY_SENSORS = [
    SensorEntityDescription(
        key=sc.ODOMETER,
        device_class=None,
        icon="mdi:road-variant",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
]

# Sensors available to "Subaru Safety Plus" subscribers with Gen2 vehicles
API_GEN_2_SENSORS = [
    SensorEntityDescription(
        key=sc.AVG_FUEL_CONSUMPTION,
        device_class=None,
        icon="mdi:leaf",
        native_unit_of_measurement=FUEL_CONSUMPTION_L_PER_100KM,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.DIST_TO_EMPTY,
        device_class=None,
        icon="mdi:gas-station",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_FL,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_FR,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_RL,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.TIRE_PRESSURE_RR,
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EXTERNAL_TEMP,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]

# Sensors available to "Subaru Safety Plus" subscribers with PHEV vehicles
EV_SENSORS = [
    SensorEntityDescription(
        key=sc.EV_DISTANCE_TO_EMPTY,
        device_class=None,
        icon="mdi:ev-station",
        native_unit_of_measurement=LENGTH_MILES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EV_STATE_OF_CHARGE_PERCENT,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key=sc.EV_TIME_TO_FULLY_CHARGED_UTC,
        device_class=SensorDeviceClass.TIMESTAMP,
        native_unit_of_measurement=None,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Subaru sensors by config_entry."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry[ENTRY_COORDINATOR]
    vehicle_info = entry[ENTRY_VEHICLES]
    entities = []
    for vin in vehicle_info:
        entities.extend(create_vehicle_sensors(vehicle_info[vin], coordinator))
    async_add_entities(entities)


def create_vehicle_sensors(vehicle_info, coordinator):
    """Instantiate all available sensors for the vehicle."""
    sensor_descriptions_to_add = []
    if vehicle_info[VEHICLE_HAS_SAFETY_SERVICE]:
        sensor_descriptions_to_add.extend(SAFETY_SENSORS)

        if vehicle_info[VEHICLE_API_GEN] == API_GEN_2:
            sensor_descriptions_to_add.extend(API_GEN_2_SENSORS)

        if vehicle_info[VEHICLE_HAS_EV]:
            sensor_descriptions_to_add.extend(EV_SENSORS)

    return [
        SubaruSensor(
            vehicle_info,
            coordinator,
            description,
        )
        for description in sensor_descriptions_to_add
    ]


class SubaruSensor(CoordinatorEntity, SensorEntity):
    """Class for Subaru sensors."""

    def __init__(
        self,
        vehicle_info,
        coordinator,
        description,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        suffix = SENSOR_KEY_TO_SUFFIX[description.key]
        self.vin = vehicle_info[VEHICLE_VIN]
        self.entity_description = description
        self._attr_device_info = get_device_info(vehicle_info)
        self._attr_name = f"{vehicle_info[VEHICLE_NAME]} {suffix}"
        self._attr_should_poll = False
        self._attr_unique_id = f"{self.vin}_{suffix}"
        _LOGGER.debug("Initialized SubaruSensor for %s", self._attr_name)

    @property
    def native_value(self):
        """Return the state of the sensor."""
        current_value = self.get_current_value()
        unit = self.entity_description.native_unit_of_measurement
        unit_system = self.hass.config.units

        if current_value is None:
            return None

        if unit in LENGTH_UNITS:
            return round(unit_system.length(current_value, unit), 1)

        if unit in PRESSURE_UNITS and unit_system == IMPERIAL_SYSTEM:
            return round(
                unit_system.pressure(current_value, unit),
                1,
            )

        if unit in FUEL_CONSUMPTION_UNITS and unit_system == IMPERIAL_SYSTEM:
            return round((100.0 * L_PER_GAL) / (KM_PER_MI * current_value), 1)

        return current_value

    @property
    def native_unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        unit = self.entity_description.native_unit_of_measurement

        if unit in LENGTH_UNITS:
            return self.hass.config.units.length_unit

        if unit in PRESSURE_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return self.hass.config.units.pressure_unit

        if unit in FUEL_CONSUMPTION_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return FUEL_CONSUMPTION_MPG

        return unit

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        last_update_success = super().available
        if last_update_success and self.vin not in self.coordinator.data:
            return False
        if self.state is None:
            return False
        return last_update_success

    def get_current_value(self):
        """Get raw value from the coordinator."""
        if isinstance(data := self.coordinator.data, dict):
            value = data.get(self.vin)[VEHICLE_STATUS].get(self.entity_description.key)
            if value in sc.BAD_SENSOR_VALUES:
                value = None
            if isinstance(value, str):
                if "." in value:
                    value = float(value)
                elif value.isdigit():
                    value = int(value)
            _LOGGER.debug("Raw value for %s: %s", self._attr_name, value)
            return value
