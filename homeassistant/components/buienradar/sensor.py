"""Support for Buienradar.nl weather service."""
from __future__ import annotations

import logging

from buienradar.constants import (
    ATTRIBUTION,
    CONDCODE,
    CONDITION,
    DETAILED,
    EXACT,
    EXACTNL,
    FORECAST,
    IMAGE,
    MEASURED,
    PRECIPITATION_FORECAST,
    STATIONNAME,
    TIMEFRAME,
    VISIBILITY,
    WINDGUST,
    WINDSPEED,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    IRRADIATION_WATTS_PER_SQUARE_METER,
    LENGTH_KILOMETERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_TIMEFRAME, DEFAULT_TIMEFRAME
from .util import BrData

_LOGGER = logging.getLogger(__name__)

MEASURED_LABEL = "Measured"
TIMEFRAME_LABEL = "Timeframe"
SYMBOL = "symbol"

# Schedule next call after (minutes):
SCHEDULE_OK = 10
# When an error occurred, new call after (minutes):
SCHEDULE_NOK = 2

STATIONNAME_LABEL = "Stationname"

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="stationname",
        name=STATIONNAME_LABEL,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfc",
        name="Barometer value",
        icon="mdi:gauge",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcname",
        name="Barometer",
        icon="mdi:gauge",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcnamenl",
        name="Barometer",
        icon="mdi:gauge",
    ),
    SensorEntityDescription(
        key="condition",
        name="Condition",
    ),
    SensorEntityDescription(
        key="conditioncode",
        name="Condition code",
    ),
    SensorEntityDescription(
        key="conditiondetailed",
        name="Detailed condition",
    ),
    SensorEntityDescription(
        key="conditionexact",
        name="Full condition",
    ),
    SensorEntityDescription(
        key="symbol",
        name="Symbol",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="feeltemperature",
        name="Feel temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:water-percent",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        name="Temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="groundtemperature",
        name="Ground temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windspeed",
        name="Wind speed",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windforce",
        name="Wind force",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="winddirection",
        name="Wind direction",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth",
        name="Wind direction azimuth",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="pressure",
        name="Pressure",
        native_unit_of_measurement=PRESSURE_HPA,
        icon="mdi:gauge",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="visibility",
        name="Visibility",
        native_unit_of_measurement=LENGTH_KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgust",
        name="Wind gust",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="precipitation",
        name="Precipitation",
        native_unit_of_measurement=PRECIPITATION_MILLIMETERS_PER_HOUR,
        icon="mdi:weather-pouring",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="irradiance",
        name="Irradiance",
        native_unit_of_measurement=IRRADIATION_WATTS_PER_SQUARE_METER,
        icon="mdi:sunglasses",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_average",
        name="Precipitation forecast average",
        native_unit_of_measurement=PRECIPITATION_MILLIMETERS_PER_HOUR,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="precipitation_forecast_total",
        name="Precipitation forecast total",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlast24hour",
        name="Rain last 24h",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlasthour",
        name="Rain last hour",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="temperature_1d",
        name="Temperature 1d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_2d",
        name="Temperature 2d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_3d",
        name="Temperature 3d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_4d",
        name="Temperature 4d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_5d",
        name="Temperature 5d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_1d",
        name="Minimum temperature 1d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_2d",
        name="Minimum temperature 2d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_3d",
        name="Minimum temperature 3d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_4d",
        name="Minimum temperature 4d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_5d",
        name="Minimum temperature 5d",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="rain_1d",
        name="Rain 1d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rain_2d",
        name="Rain 2d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rain_3d",
        name="Rain 3d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rain_4d",
        name="Rain 4d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rain_5d",
        name="Rain 5d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="minrain_1d",
        name="Minimum rain 1d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="minrain_2d",
        name="Minimum rain 2d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="minrain_3d",
        name="Minimum rain 3d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="minrain_4d",
        name="Minimum rain 4d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="minrain_5d",
        name="Minimum rain 5d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="maxrain_1d",
        name="Maximum rain 1d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="maxrain_2d",
        name="Maximum rain 2d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="maxrain_3d",
        name="Maximum rain 3d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="maxrain_4d",
        name="Maximum rain 4d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="maxrain_5d",
        name="Maximum rain 5d",
        native_unit_of_measurement=LENGTH_MILLIMETERS,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rainchance_1d",
        name="Rainchance 1d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rainchance_2d",
        name="Rainchance 2d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rainchance_3d",
        name="Rainchance 3d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rainchance_4d",
        name="Rainchance 4d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="rainchance_5d",
        name="Rainchance 5d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-pouring",
    ),
    SensorEntityDescription(
        key="sunchance_1d",
        name="Sunchance 1d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="sunchance_2d",
        name="Sunchance 2d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="sunchance_3d",
        name="Sunchance 3d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="sunchance_4d",
        name="Sunchance 4d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="sunchance_5d",
        name="Sunchance 5d",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="windforce_1d",
        name="Wind force 1d",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windforce_2d",
        name="Wind force 2d",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windforce_3d",
        name="Wind force 3d",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windforce_4d",
        name="Wind force 4d",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windforce_5d",
        name="Wind force 5d",
        native_unit_of_measurement="Bft",
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windspeed_1d",
        name="Wind speed 1d",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windspeed_2d",
        name="Wind speed 2d",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windspeed_3d",
        name="Wind speed 3d",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windspeed_4d",
        name="Wind speed 4d",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="windspeed_5d",
        name="Wind speed 5d",
        native_unit_of_measurement=SPEED_KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        icon="mdi:weather-windy",
    ),
    SensorEntityDescription(
        key="winddirection_1d",
        name="Wind direction 1d",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="winddirection_2d",
        name="Wind direction 2d",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="winddirection_3d",
        name="Wind direction 3d",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="winddirection_4d",
        name="Wind direction 4d",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="winddirection_5d",
        name="Wind direction 5d",
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth_1d",
        name="Wind direction azimuth 1d",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth_2d",
        name="Wind direction azimuth 2d",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth_3d",
        name="Wind direction azimuth 3d",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth_4d",
        name="Wind direction azimuth 4d",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="windazimuth_5d",
        name="Wind direction azimuth 5d",
        native_unit_of_measurement=DEGREE,
        icon="mdi:compass-outline",
    ),
    SensorEntityDescription(
        key="condition_1d",
        name="Condition 1d",
    ),
    SensorEntityDescription(
        key="condition_2d",
        name="Condition 2d",
    ),
    SensorEntityDescription(
        key="condition_3d",
        name="Condition 3d",
    ),
    SensorEntityDescription(
        key="condition_4d",
        name="Condition 4d",
    ),
    SensorEntityDescription(
        key="condition_5d",
        name="Condition 5d",
    ),
    SensorEntityDescription(
        key="conditioncode_1d",
        name="Condition code 1d",
    ),
    SensorEntityDescription(
        key="conditioncode_2d",
        name="Condition code 2d",
    ),
    SensorEntityDescription(
        key="conditioncode_3d",
        name="Condition code 3d",
    ),
    SensorEntityDescription(
        key="conditioncode_4d",
        name="Condition code 4d",
    ),
    SensorEntityDescription(
        key="conditioncode_5d",
        name="Condition code 5d",
    ),
    SensorEntityDescription(
        key="conditiondetailed_1d",
        name="Detailed condition 1d",
    ),
    SensorEntityDescription(
        key="conditiondetailed_2d",
        name="Detailed condition 2d",
    ),
    SensorEntityDescription(
        key="conditiondetailed_3d",
        name="Detailed condition 3d",
    ),
    SensorEntityDescription(
        key="conditiondetailed_4d",
        name="Detailed condition 4d",
    ),
    SensorEntityDescription(
        key="conditiondetailed_5d",
        name="Detailed condition 5d",
    ),
    SensorEntityDescription(
        key="conditionexact_1d",
        name="Full condition 1d",
    ),
    SensorEntityDescription(
        key="conditionexact_2d",
        name="Full condition 2d",
    ),
    SensorEntityDescription(
        key="conditionexact_3d",
        name="Full condition 3d",
    ),
    SensorEntityDescription(
        key="conditionexact_4d",
        name="Full condition 4d",
    ),
    SensorEntityDescription(
        key="conditionexact_5d",
        name="Full condition 5d",
    ),
    SensorEntityDescription(
        key="symbol_1d",
        name="Symbol 1d",
    ),
    SensorEntityDescription(
        key="symbol_2d",
        name="Symbol 2d",
    ),
    SensorEntityDescription(
        key="symbol_3d",
        name="Symbol 3d",
    ),
    SensorEntityDescription(
        key="symbol_4d",
        name="Symbol 4d",
    ),
    SensorEntityDescription(
        key="symbol_5d",
        name="Symbol 5d",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the buienradar sensor."""
    config = entry.data
    options = entry.options

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    timeframe = options.get(
        CONF_TIMEFRAME, config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME)
    )

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    _LOGGER.debug(
        "Initializing buienradar sensor coordinate %s, timeframe %s",
        coordinates,
        timeframe,
    )

    entities = [
        BrSensor(config.get(CONF_NAME, "Buienradar"), coordinates, description)
        for description in SENSOR_TYPES
    ]

    async_add_entities(entities)

    data = BrData(hass, coordinates, timeframe, entities)
    # schedule the first update in 1 minute from now:
    await data.schedule_update(1)


class BrSensor(SensorEntity):
    """Representation of an Buienradar sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False

    def __init__(self, client_name, coordinates, description: SensorEntityDescription):
        """Initialize the sensor."""
        self.entity_description = description
        self._attr_name = f"{client_name} {description.name}"
        self._measured = None
        self._attr_unique_id = "{:2.6f}{:2.6f}{}".format(
            coordinates[CONF_LATITUDE], coordinates[CONF_LONGITUDE], description.key
        )

        # All continuous sensors should be forced to be updated
        self._attr_force_update = (
            description.key != SYMBOL and not description.key.startswith(CONDITION)
        )

        if description.key.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    @callback
    def data_updated(self, data):
        """Update data."""
        if self.hass and self._load_data(data):
            self.async_write_ha_state()

    @callback
    def _load_data(self, data):  # noqa: C901
        """Load the sensor with relevant data."""
        # Find sensor

        # Check if we have a new measurement,
        # otherwise we do not have to update the sensor
        if self._measured == data.get(MEASURED):
            return False

        self._measured = data.get(MEASURED)
        sensor_type = self.entity_description.key

        if (
            sensor_type.endswith("_1d")
            or sensor_type.endswith("_2d")
            or sensor_type.endswith("_3d")
            or sensor_type.endswith("_4d")
            or sensor_type.endswith("_5d")
        ):

            # update forecasting sensors:
            fcday = 0
            if sensor_type.endswith("_2d"):
                fcday = 1
            if sensor_type.endswith("_3d"):
                fcday = 2
            if sensor_type.endswith("_4d"):
                fcday = 3
            if sensor_type.endswith("_5d"):
                fcday = 4

            # update weather symbol & status text
            if sensor_type.startswith(SYMBOL) or sensor_type.startswith(CONDITION):
                try:
                    condition = data.get(FORECAST)[fcday].get(CONDITION)
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s", fcday)
                    return False

                if condition:
                    new_state = condition.get(CONDITION)
                    if sensor_type.startswith(SYMBOL):
                        new_state = condition.get(EXACTNL)
                    if sensor_type.startswith("conditioncode"):
                        new_state = condition.get(CONDCODE)
                    if sensor_type.startswith("conditiondetailed"):
                        new_state = condition.get(DETAILED)
                    if sensor_type.startswith("conditionexact"):
                        new_state = condition.get(EXACT)

                    img = condition.get(IMAGE)

                    if new_state != self.state or img != self.entity_picture:
                        self._attr_native_value = new_state
                        self._attr_entity_picture = img
                        return True
                return False

            if sensor_type.startswith(WINDSPEED):
                # hass wants windspeeds in km/h not m/s, so convert:
                try:
                    self._attr_native_value = data.get(FORECAST)[fcday].get(
                        sensor_type[:-3]
                    )
                    if self.state is not None:
                        self._attr_native_value = round(self.state * 3.6, 1)
                    return True
                except IndexError:
                    _LOGGER.warning("No forecast for fcday=%s", fcday)
                    return False

            # update all other sensors
            try:
                self._attr_native_value = data.get(FORECAST)[fcday].get(
                    sensor_type[:-3]
                )
                return True
            except IndexError:
                _LOGGER.warning("No forecast for fcday=%s", fcday)
                return False

        if sensor_type == SYMBOL or sensor_type.startswith(CONDITION):
            # update weather symbol & status text
            if condition := data.get(CONDITION):
                if sensor_type == SYMBOL:
                    new_state = condition.get(EXACTNL)
                if sensor_type == CONDITION:
                    new_state = condition.get(CONDITION)
                if sensor_type == "conditioncode":
                    new_state = condition.get(CONDCODE)
                if sensor_type == "conditiondetailed":
                    new_state = condition.get(DETAILED)
                if sensor_type == "conditionexact":
                    new_state = condition.get(EXACT)

                img = condition.get(IMAGE)

                if new_state != self.state or img != self.entity_picture:
                    self._attr_native_value = new_state
                    self._attr_entity_picture = img
                    return True

            return False

        if sensor_type.startswith(PRECIPITATION_FORECAST):
            # update nested precipitation forecast sensors
            nested = data.get(PRECIPITATION_FORECAST)
            self._timeframe = nested.get(TIMEFRAME)
            self._attr_native_value = nested.get(
                sensor_type[len(PRECIPITATION_FORECAST) + 1 :]
            )
            return True

        if sensor_type in [WINDSPEED, WINDGUST]:
            # hass wants windspeeds in km/h not m/s, so convert:
            self._attr_native_value = data.get(sensor_type)
            if self.state is not None:
                self._attr_native_value = round(data.get(sensor_type) * 3.6, 1)
            return True

        if sensor_type == VISIBILITY:
            # hass wants visibility in km (not m), so convert:
            self._attr_native_value = data.get(sensor_type)
            if self.state is not None:
                self._attr_native_value = round(self.state / 1000, 1)
            return True

        # update all other sensors
        self._attr_native_value = data.get(sensor_type)
        if sensor_type.startswith(PRECIPITATION_FORECAST):
            result = {ATTR_ATTRIBUTION: data.get(ATTRIBUTION)}
            if self._timeframe is not None:
                result[TIMEFRAME_LABEL] = "%d min" % (self._timeframe)

            self._attr_extra_state_attributes = result

        result = {
            ATTR_ATTRIBUTION: data.get(ATTRIBUTION),
            STATIONNAME_LABEL: data.get(STATIONNAME),
        }
        if self._measured is not None:
            # convert datetime (Europe/Amsterdam) into local datetime
            local_dt = dt_util.as_local(self._measured)
            result[MEASURED_LABEL] = local_dt.strftime("%c")

        self._attr_extra_state_attributes = result
        return True
