"""Support for Ecowitt Weather Stations."""
from __future__ import annotations

import logging
from dataclasses import dataclass
import homeassistant.util.dt as dt_util

from pyecowitt import EcoWittSensor

from . import EcowittEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    SensorEntity,
    SensorEntityDescription,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
)

from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_WIND,
    CONF_UNIT_RAIN,
    CONF_UNIT_LIGHTNING,
    CONF_UNIT_SYSTEM_METRIC_MS,
    DOMAIN,
    SIGNAL_ADD_ENTITIES,
)

from homeassistant.const import (
    STATE_UNKNOWN,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_PRESSURE,
    PERCENTAGE,
    CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_SYSTEM_IMPERIAL,
    DEGREE,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    PRESSURE_HPA,
    PRESSURE_INHG,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    UV_INDEX,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    ELECTRIC_POTENTIAL_VOLT,
    LENGTH_MILLIMETERS,
    TIME_HOURS,
    TIME_DAYS,
    TIME_WEEKS,
    TIME_MONTHS,
    TIME_YEARS,
)

_LOGGER = logging.getLogger(__name__)

# Map the EcowittSensorTypes into HA types
UOM_MAP = {
    "pressure_hpa": PRESSURE_HPA,
    "pressure_inhg": PRESSURE_INHG,
    "rate_inches": None,
    "rate_mm": None,
    "humidity": PERCENTAGE,
    "degree": DEGREE,
    "speed_kph": SPEED_KILOMETERS_PER_HOUR,
    "speed_mph": SPEED_MILES_PER_HOUR,
    "speed_mps": SPEED_METERS_PER_SECOND,
    "temperature_c": TEMP_CELSIUS,
    "temperature_f": TEMP_FAHRENHEIT,
    "watt_meters_squared": IRRADIATION_WATTS_PER_SQUARE_METER,
    "uv_index": UV_INDEX,
    "pm25": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "timestamp": None,
    "count": None,
    "distance_km": LENGTH_KILOMETERS,
    "distance_miles": LENGTH_MILES,
    "binary": None,
    "pm10": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    "voltage": ELECTRIC_POTENTIAL_VOLT,
    "battery_percentage": PERCENTAGE,
    "length_inches": LENGTH_INCHES,
    "length_mm": LENGTH_MILLIMETERS,
    "ppm": CONCENTRATION_PARTS_PER_MILLION,
    "internal": None,
}

SENSOR_TYPE_MAP = {
    CONF_UNIT_BARO: {
        CONF_UNIT_SYSTEM_IMPERIAL: "pressure_inhg",
        CONF_UNIT_SYSTEM_METRIC: "pressure_hpa",
    },
    CONF_UNIT_WIND: {
        CONF_UNIT_SYSTEM_IMPERIAL: "speed_mph",
        CONF_UNIT_SYSTEM_METRIC: "speed_kph",
        CONF_UNIT_SYSTEM_METRIC_MS: "speed_mps",
    },
    CONF_UNIT_LIGHTNING: {
        CONF_UNIT_SYSTEM_IMPERIAL: "distance_miles",
        CONF_UNIT_SYSTEM_METRIC: "distance_km",
    },
    CONF_UNIT_RAIN: {
        CONF_UNIT_SYSTEM_IMPERIAL: "rate_inches",
        CONF_UNIT_SYSTEM_METRIC: "rate_mm",
    }
}

UNIT_LIST = [CONF_UNIT_BARO, CONF_UNIT_WIND, CONF_UNIT_LIGHTNING, CONF_UNIT_RAIN]

RAIN_MAP = {
    "rainratein": [STATE_CLASS_MEASUREMENT, f"{LENGTH_INCHES}/{TIME_HOURS}"],
    "eventrainin": [STATE_CLASS_MEASUREMENT, f"{LENGTH_INCHES}/{TIME_HOURS}"],
    "hourlyrainin": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_INCHES}/{TIME_HOURS}"],
    "totalrainin": [STATE_CLASS_TOTAL_INCREASING, LENGTH_INCHES],
    "dailyrainin": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_INCHES}/{TIME_DAYS}"],
    "weeklyrainin": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_INCHES}/{TIME_WEEKS}"],
    "monthlyrainin": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_INCHES}/{TIME_MONTHS}"],
    "yearlyrainin": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_INCHES}/{TIME_YEARS}"],
    "rainratemm": [STATE_CLASS_MEASUREMENT, f"{LENGTH_MILLIMETERS}/{TIME_HOURS}"],
    "eventrainmm": [STATE_CLASS_MEASUREMENT, f"{LENGTH_MILLIMETERS}/{TIME_HOURS}"],
    "hourlyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_HOURS}"],
    "totalrainmm": [STATE_CLASS_TOTAL_INCREASING, LENGTH_MILLIMETERS],
    "dailyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_DAYS}"],
    "weeklyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_WEEKS}"],
    "monthlyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_MONTHS}"],
    "yearlyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_YEARS}"],
}


@dataclass
class EcowittSensorTypeMixin:
    """Mixin for sensor required keys."""

    cls: type[EcowittSensor]


@dataclass
class EcowittSensorEntityDescription(SensorEntityDescription, EcowittSensorTypeMixin):
    """Base description of a Sensor entity."""


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]

    entities: list[Entity] = []

    sensor_types = []
    for unit in UNIT_LIST:
        sensor_types.append(SENSOR_TYPE_MAP[unit][entry.options[unit]])

    sensors = data.client.list_sensor_keys()

    for sensor_key in sensors:
        for description in SENSOR_ENTITIES:
            device = data.client.find_sensor(sensor_key)
            if device is None or device.get_key() != sensor_key or device.get_stype() != description.key:
                continue
            if (device.get_system() is None or device.get_stype() == "temperature_c"):
                data.registered_devices.append(sensor_key)
                entities.append(description.cls(hass, entry, device, description))
                continue
            for unit in sensor_types:
                if device.get_stype() == unit:
                    data.registered_devices.append(sensor_key)
                    entities.append(description.cls(hass, entry, device, description))

    async_add_entities(entities)

    # def add_entities(discovery_info=None):
    #     async_add_ecowitt_entities(hass, entry, EcowittSensor,
    #                                SENSOR_DOMAIN, async_add_entities,
    #                                discovery_info)

    # signal = f"{SIGNAL_ADD_ENTITIES}_{SENSOR_DOMAIN}"
    # async_dispatcher_connect(hass, signal, add_entities)
    # add_entities(hass.data[DOMAIN][entry.entry_id][REG_ENTITIES][TYPE_SENSOR])


class EcowittSensor(EcowittEntity, SensorEntity):
    """Base class for the ecowitt sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: EcoWittSensor,
        entity_description: EcowittSensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(hass, entry, device)
        self.entity_description = entity_description
        self.device = device
        self._attr_native_unit_of_measurement = UOM_MAP[self.device.get_stype()]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._key not in self.data.client.last_values:
            _LOGGER.warning("Sensor %s not in last update, check range or battery",
                            self._key)
            return STATE_UNKNOWN

        return self.device.get_value()


class EcowittHumiditySensor(EcowittSensor):
    """Represent an Ecowitt humidity sensor."""


class EcowittTemperatureSensor(EcowittSensor):
    """Represent an Ecowitt temperature sensor."""


class EcowittPressureSensor(EcowittSensor):
    """Represent an Ecowitt temperature sensor."""


class EcowittRainRateSensor(EcowittSensor):
    """Represent an Ecowitt rain rate sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: EcoWittSensor,
        entity_description: EcowittSensorEntityDescription
    ) -> None:
        super().__init__(hass, entry, device, entity_description)
        self._attr_state_class = RAIN_MAP[self.device.get_key()][0]
        self._attr_native_unit_of_measurement = RAIN_MAP[self.device.get_key()][1]


SENSOR_ENTITIES: tuple[EcowittSensorEntityDescription, ...] = (
    EcowittSensorEntityDescription(
        key="pressure_hpa",
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:gauge",
        cls=EcowittPressureSensor,
    ),
    EcowittSensorEntityDescription(
        key="pressure_inhg",
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:gauge",
        cls=EcowittPressureSensor,
    ),
    EcowittSensorEntityDescription(
        key="temperature_c",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:thermometer",
        cls=EcowittTemperatureSensor,
    ),
    EcowittSensorEntityDescription(
        key="humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:water-percent",
        cls=EcowittHumiditySensor,
    ),
    EcowittSensorEntityDescription(
        key="rate_mm",
        icon="mdi:water",
        cls=EcowittRainRateSensor,
    ),
    EcowittSensorEntityDescription(
        key="rate_inches",
        icon="mdi:water",
        cls=EcowittRainRateSensor,
    ),
)
