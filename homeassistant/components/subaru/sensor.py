"""Support for the Subaru sensors."""
import logging

import subarulink.const as sc

from homeassistant.const import (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
    TIME_MINUTES,
    VOLT,
    VOLUME_GALLONS,
    VOLUME_LITERS,
)
from homeassistant.util.distance import convert as dist_convert
from homeassistant.util.unit_system import (
    IMPERIAL_SYSTEM,
    LENGTH_UNITS,
    PRESSURE_UNITS,
    TEMPERATURE_UNITS,
)
from homeassistant.util.volume import convert as vol_convert

from .const import (
    API_GEN_2,
    DOMAIN,
    ENTRY_COORDINATOR,
    ENTRY_VEHICLES,
    VEHICLE_API_GEN,
    VEHICLE_HAS_EV,
    VEHICLE_HAS_SAFETY_SERVICE,
)
from .entity import SubaruEntity

_LOGGER = logging.getLogger(__name__)
L_PER_GAL = vol_convert(1, VOLUME_GALLONS, VOLUME_LITERS)
KM_PER_MI = dist_convert(1, LENGTH_MILES, LENGTH_KILOMETERS)

# Fuel Economy Constants
FUEL_CONSUMPTION_L_PER_100KM = "L/100km"
FUEL_CONSUMPTION_MPG = "mi/gal"
FUEL_CONSUMPTION_UNITS = [FUEL_CONSUMPTION_L_PER_100KM, FUEL_CONSUMPTION_MPG]

SENSOR_NAME = "name"
SENSOR_FIELD = "field"
SENSOR_UNITS = "units"

# Sensor data available to "Subaru Safety Plus" subscribers with Gen1 or Gen2 vehicles
SAFETY_SENSORS = [
    {
        SENSOR_NAME: "Avg Fuel Consumption",
        SENSOR_FIELD: sc.AVG_FUEL_CONSUMPTION,
        SENSOR_UNITS: FUEL_CONSUMPTION_L_PER_100KM,
    },
    {
        SENSOR_NAME: "Range",
        SENSOR_FIELD: sc.DIST_TO_EMPTY,
        SENSOR_UNITS: LENGTH_KILOMETERS,
    },
    {
        SENSOR_NAME: "Odometer",
        SENSOR_FIELD: sc.ODOMETER,
        SENSOR_UNITS: LENGTH_KILOMETERS,
    },
    {
        SENSOR_NAME: "Tire Pressure FL",
        SENSOR_FIELD: sc.TIRE_PRESSURE_FL,
        SENSOR_UNITS: PRESSURE_HPA,
    },
    {
        SENSOR_NAME: "Tire Pressure FR",
        SENSOR_FIELD: sc.TIRE_PRESSURE_FR,
        SENSOR_UNITS: PRESSURE_HPA,
    },
    {
        SENSOR_NAME: "Tire Pressure RL",
        SENSOR_FIELD: sc.TIRE_PRESSURE_RL,
        SENSOR_UNITS: PRESSURE_HPA,
    },
    {
        SENSOR_NAME: "Tire Pressure RR",
        SENSOR_FIELD: sc.TIRE_PRESSURE_RR,
        SENSOR_UNITS: PRESSURE_HPA,
    },
]

# Sensor data available to "Subaru Safety Plus" subscribers with Gen2 vehicles
API_GEN_2_SENSORS = [
    {
        SENSOR_NAME: "External Temp",
        SENSOR_FIELD: sc.EXTERNAL_TEMP,
        SENSOR_UNITS: TEMP_CELSIUS,
    },
    {
        SENSOR_NAME: "12V Battery Voltage",
        SENSOR_FIELD: sc.BATTERY_VOLTAGE,
        SENSOR_UNITS: VOLT,
    },
]

# Sensor data available to "Subaru Safety Plus" subscribers with PHEV vehicles
EV_SENSORS = [
    {
        SENSOR_NAME: "EV Range",
        SENSOR_FIELD: sc.EV_DISTANCE_TO_EMPTY,
        SENSOR_UNITS: LENGTH_MILES,
    },
    {
        SENSOR_NAME: "EV Battery Level",
        SENSOR_FIELD: sc.EV_STATE_OF_CHARGE_PERCENT,
        SENSOR_UNITS: PERCENTAGE,
    },
    {
        SENSOR_NAME: "EV Time to Full Charge",
        SENSOR_FIELD: sc.EV_TIME_TO_FULLY_CHARGED,
        SENSOR_UNITS: TIME_MINUTES,
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Subaru sensors by config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ENTRY_COORDINATOR]
    vehicle_info = hass.data[DOMAIN][config_entry.entry_id][ENTRY_VEHICLES]
    entities = []
    for vin in vehicle_info.keys():
        _create_sensor_entities(entities, vehicle_info[vin], coordinator, hass)
    async_add_entities(entities, True)


def _create_sensor_entities(entities, vehicle_info, coordinator, hass):
    sensors_to_add = []
    if vehicle_info[VEHICLE_HAS_SAFETY_SERVICE]:
        sensors_to_add.extend(SAFETY_SENSORS)

        if vehicle_info[VEHICLE_API_GEN] == API_GEN_2:
            sensors_to_add.extend(API_GEN_2_SENSORS)

        if vehicle_info[VEHICLE_HAS_EV]:
            sensors_to_add.extend(EV_SENSORS)

    for s in sensors_to_add:
        entities.append(
            SubaruSensor(
                vehicle_info,
                coordinator,
                hass,
                s[SENSOR_NAME],
                s[SENSOR_FIELD],
                s[SENSOR_UNITS],
            )
        )


class SubaruSensor(SubaruEntity):
    """Class for Subaru sensors."""

    def __init__(self, vehicle_info, coordinator, hass, title, data_field, api_unit):
        """Initialize the sensor."""
        super().__init__(vehicle_info, coordinator)
        self.hass_type = "sensor"
        self.current_value = None
        self.hass = hass
        self.title = title
        self.data_field = data_field
        self.api_unit = api_unit

    @property
    def state(self):
        """Return the state of the sensor."""
        self.current_value = self.get_current_value()

        if self.current_value is None:
            return None

        if self.api_unit in TEMPERATURE_UNITS:
            return round(
                self.hass.config.units.temperature(self.current_value, self.api_unit), 1
            )

        if self.api_unit in LENGTH_UNITS:
            return round(
                self.hass.config.units.length(self.current_value, self.api_unit), 1
            )

        if self.api_unit in PRESSURE_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return round(
                    self.hass.config.units.pressure(self.current_value, self.api_unit),
                    1,
                )

        if self.api_unit in FUEL_CONSUMPTION_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return round((100.0 * L_PER_GAL) / (KM_PER_MI * self.current_value), 1)

        return self.current_value

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        if self.api_unit in TEMPERATURE_UNITS:
            return self.hass.config.units.temperature_unit

        if self.api_unit in LENGTH_UNITS:
            return self.hass.config.units.length_unit

        if self.api_unit in PRESSURE_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return self.hass.config.units.pressure_unit
            return PRESSURE_HPA

        if self.api_unit in FUEL_CONSUMPTION_UNITS:
            if self.hass.config.units == IMPERIAL_SYSTEM:
                return FUEL_CONSUMPTION_MPG
            return FUEL_CONSUMPTION_L_PER_100KM

        return self.api_unit

    def get_current_value(self):
        """Get raw value from the coordinator."""
        value = self.coordinator.data[self.vin]["status"][self.data_field]
        if value in sc.BAD_SENSOR_VALUES:
            value = None
        if isinstance(value, str):
            if "." in value:
                value = float(value)
            else:
                value = int(value)
        return value
