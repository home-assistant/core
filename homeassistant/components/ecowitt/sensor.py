"""Support for Ecowitt Weather Stations."""
from __future__ import annotations

from dataclasses import dataclass
import logging

from pyecowitt import EcoWittSensor

from homeassistant.components.sensor import (
    DOMAIN as SENSOR_DOMAIN,
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC,
    DEGREE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
    ELECTRIC_POTENTIAL_VOLT,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_DAYS,
    TIME_HOURS,
    TIME_MONTHS,
    TIME_WEEKS,
    TIME_YEARS,
    UV_INDEX,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_registry import (
    async_get_registry as async_get_entity_registry,
)
import homeassistant.util.dt as dt_util

from . import EcowittEntity
from .const import (
    CONF_UNIT_BARO,
    CONF_UNIT_LIGHTNING,
    CONF_UNIT_RAIN,
    CONF_UNIT_SYSTEM_METRIC_MS,
    CONF_UNIT_WIND,
    DATA_PASSKEY,
    DOMAIN,
    SIGNAL_ADD_ENTITIES,
    SIGNAL_NEW_SENSOR,
    SIGNAL_REMOVE_ENTITIES,
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
    "co2_ppm": CONCENTRATION_PARTS_PER_MILLION,
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
    },
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
    "hourlyrainmm": [
        STATE_CLASS_TOTAL_INCREASING,
        f"{LENGTH_MILLIMETERS}/{TIME_HOURS}",
    ],
    "totalrainmm": [STATE_CLASS_TOTAL_INCREASING, LENGTH_MILLIMETERS],
    "dailyrainmm": [STATE_CLASS_TOTAL_INCREASING, f"{LENGTH_MILLIMETERS}/{TIME_DAYS}"],
    "weeklyrainmm": [
        STATE_CLASS_TOTAL_INCREASING,
        f"{LENGTH_MILLIMETERS}/{TIME_WEEKS}",
    ],
    "monthlyrainmm": [
        STATE_CLASS_TOTAL_INCREASING,
        f"{LENGTH_MILLIMETERS}/{TIME_MONTHS}",
    ],
    "yearlyrainmm": [
        STATE_CLASS_TOTAL_INCREASING,
        f"{LENGTH_MILLIMETERS}/{TIME_YEARS}",
    ],
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

    async def _async_remove_old_entities(discovery_info=None):
        """Remove old entities from HomeAssistant.

        When the user changes a config option, it will orphan entities of the
        wrong imperial/metric type, this deletes them.
        """
        data = hass.data[DOMAIN][entry.entry_id]
        old_sensor_types = []
        entities_to_kill = []

        # generate a reverse list
        for unit in UNIT_LIST:
            for configured_unit in SENSOR_TYPE_MAP[unit].keys():
                if entry.options[unit] != configured_unit:
                    old_sensor_types.append(SENSOR_TYPE_MAP[unit][configured_unit])

        for sensor_key in data.registered_devices:
            device = data.client.find_sensor(sensor_key)
            if device is None:
                continue
            if device.get_stype() in old_sensor_types:
                entities_to_kill.append(sensor_key)

        for key in entities_to_kill:
            registry = await async_get_entity_registry(hass)
            unique_id = f"{data.client.get_sensor_value_by_key(DATA_PASSKEY)}-{key}"
            entity_id = registry.async_get_entity_id(SENSOR_DOMAIN, DOMAIN, unique_id)

            if entity_id:
                _LOGGER.debug(
                    "Found entity %s for key %s -> unique_id %s",
                    entity_id,
                    key,
                    unique_id,
                )
                registry.async_remove(entity_id)
                data.registered_devices.remove(key)

    async def _async_add_ecowitt_entities(discovery_info: list[str]):
        """Add sensor entities to HomeAssistant."""
        _LOGGER.debug("Called async_add_ecowitt_entities")
        data = hass.data[DOMAIN][entry.entry_id]
        entities: list[Entity] = []

        sensor_types = []
        for unit in UNIT_LIST:
            sensor_types.append(SENSOR_TYPE_MAP[unit][entry.options[unit]])

        for sensor_key in discovery_info:
            if sensor_key in data.registered_devices:
                continue
            for description in SENSOR_ENTITIES:
                device = data.client.find_sensor(sensor_key)
                if (
                    device is None
                    or device.get_key() != sensor_key
                    or device.get_stype() != description.key
                ):
                    continue
                if device.get_system() is None or device.get_stype() == "temperature_c":
                    data.registered_devices.append(sensor_key)
                    entities.append(description.cls(hass, entry, device, description))
                    continue
                for unit in sensor_types:
                    if device.get_stype() == unit:
                        data.registered_devices.append(sensor_key)
                        entities.append(
                            description.cls(hass, entry, device, description)
                        )

        async_add_entities(entities)

    def _new_sensor():
        """Create callback for new sensors discovered."""
        _LOGGER.debug("_new_sensor called")
        data = hass.data[DOMAIN][entry.entry_id]
        sensors = data.client.list_sensor_keys()
        async_dispatcher_send(
            hass, SIGNAL_ADD_ENTITIES.format(SENSOR_DOMAIN, entry.entry_id), sensors
        )

    data = hass.data[DOMAIN][entry.entry_id]
    sensors = data.client.list_sensor_keys()
    async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES.format(SENSOR_DOMAIN, entry.entry_id),
        _async_add_ecowitt_entities,
    )
    async_dispatcher_connect(
        hass, SIGNAL_NEW_SENSOR.format(SENSOR_DOMAIN, entry.entry_id), _new_sensor
    )
    async_dispatcher_connect(
        hass,
        SIGNAL_REMOVE_ENTITIES.format(SENSOR_DOMAIN, entry.entry_id),
        _async_remove_old_entities,
    )

    await _async_add_ecowitt_entities(sensors)


class EcowittSensor(EcowittEntity, SensorEntity):
    """Base class for the ecowitt sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: EcoWittSensor,
        entity_description: EcowittSensorEntityDescription,
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
            _LOGGER.warning(
                "Sensor %s not in last update, check range or battery", self._key
            )
            return STATE_UNKNOWN

        return self.device.get_value()


class EcowittRainRateSensor(EcowittSensor):
    """Represent an Ecowitt rain rate sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: EcoWittSensor,
        entity_description: EcowittSensorEntityDescription,
    ) -> None:
        """Initialize ecowitt rain sensor."""
        super().__init__(hass, entry, device, entity_description)
        self._attr_state_class = RAIN_MAP[self.device.get_key()][0]
        self._attr_native_unit_of_measurement = RAIN_MAP[self.device.get_key()][1]


class EcowittLightningTimeSensor(EcowittSensor):
    """Represent an Ecowitt lightning last strike time sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._key not in self.data.client.last_values:
            _LOGGER.warning(
                "Sensor %s not in last update, check range or battery", self._key
            )
            return STATE_UNKNOWN

        # strikes are reported in UTC
        return dt_util.as_local(dt_util.utc_from_timestamp(self.device.get_value()))


class EcowittLightningCountSensor(EcowittSensor):
    """Represent an Ecowitt lightning strike count sensor."""

    _attr_native_unit_of_measurement = f"strikes/{TIME_DAYS}"


class EcowittBatteryPercentSensor(EcowittSensor):
    """Represent an Ecowitt battery percentage Sensor."""

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self._key not in self.data.client.last_values:
            _LOGGER.warning(
                "Sensor %s not in last update, check range or battery", self._key
            )
            return STATE_UNKNOWN

        # battery value is 0-5
        return self.device.get_value() * 20.0


SENSOR_ENTITIES: tuple[EcowittSensorEntityDescription, ...] = (
    EcowittSensorEntityDescription(
        key="pressure_hpa",
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:gauge",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="pressure_inhg",
        device_class=DEVICE_CLASS_PRESSURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:gauge",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="temperature_c",
        device_class=DEVICE_CLASS_TEMPERATURE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:thermometer",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="humidity",
        device_class=DEVICE_CLASS_HUMIDITY,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:water-percent",
        cls=EcowittSensor,
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
    EcowittSensorEntityDescription(
        key="length_inches",
        icon="mdi:water",
        cls=EcowittRainRateSensor,
    ),
    EcowittSensorEntityDescription(
        key="length_mm",
        icon="mdi:water",
        cls=EcowittRainRateSensor,
    ),
    EcowittSensorEntityDescription(
        key="degree",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:compass",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="speed_kph",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:weather-windy",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="speed_mph",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:weather-windy",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="speed_mps",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:weather-windy",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="watt_meters_squared",
        device_class=DEVICE_CLASS_ILLUMINANCE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:weather-sunny",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="uv_index",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:sunglasses",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="pm25",
        device_class=DEVICE_CLASS_PM25,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:eye",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="timestamp",
        device_class=DEVICE_CLASS_TIMESTAMP,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:clock",
        cls=EcowittLightningTimeSensor,
    ),
    EcowittSensorEntityDescription(
        key="count",
        state_class=STATE_CLASS_TOTAL_INCREASING,
        icon="mdi:weather-lightning",
        cls=EcowittLightningCountSensor,
    ),
    EcowittSensorEntityDescription(
        key="distance_km",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:ruler",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="distance_miles",
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:ruler",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="pm10",
        device_class=DEVICE_CLASS_PM10,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:eye",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="voltage",
        device_class=DEVICE_CLASS_VOLTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:battery",
        cls=EcowittSensor,
    ),
    EcowittSensorEntityDescription(
        key="battery_percentage",
        device_class=DEVICE_CLASS_BATTERY,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:battery",
        cls=EcowittBatteryPercentSensor,
    ),
    EcowittSensorEntityDescription(
        key="co2_ppm",
        device_class=DEVICE_CLASS_CO2,
        state_class=STATE_CLASS_MEASUREMENT,
        icon="mdi:molecule-co2",
        cls=EcowittSensor,
    ),
)
