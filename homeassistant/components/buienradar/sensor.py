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
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    DEGREE,
    PERCENTAGE,
    Platform,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import BuienRadarConfigEntry
from .const import (
    CONF_TIMEFRAME,
    DEFAULT_TIMEFRAME,
    STATE_CONDITION_CODES,
    STATE_CONDITIONS,
    STATE_DETAILED_CONDITIONS,
)
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

#mdi icon names (duplication fix)
mdi_gauge = "mdi:gauge"
mdi_compass_outline = "mdi:compass-outline"
mdi_weather_windy = "mdi:weather-windy"
mdi_water_percent = "mdi:water-percent"
mdi_weather_pouring = "mdi:weather-pouring"
mdi_weather_partly_cloudy = "mdi:weather-partly-cloudy"



SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="stationname",
        translation_key="stationname",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfc",
        translation_key="barometerfc",
        icon=mdi_gauge,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcname",
        translation_key="barometerfcname",
        icon=mdi_gauge,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="barometerfcnamenl",
        translation_key="barometerfcnamenl",
        icon=mdi_gauge,
    ),
    SensorEntityDescription(
        key="condition",
        translation_key="condition",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode",
        translation_key="conditioncode",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed",
        translation_key="conditiondetailed",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact",
        translation_key="conditionexact",
    ),
    SensorEntityDescription(
        key="symbol",
        translation_key="symbol",
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="feeltemperature",
        translation_key="feeltemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_water_percent,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="groundtemperature",
        translation_key="groundtemperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windspeed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windforce",
        translation_key="windforce",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="winddirection",
        translation_key="winddirection",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="windazimuth",
        translation_key="windazimuth",
        native_unit_of_measurement=DEGREE,
        device_class=SensorDeviceClass.WIND_DIRECTION,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
    ),
    SensorEntityDescription(
        key="pressure",
        device_class=SensorDeviceClass.PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        icon=mdi_gauge,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="visibility",
        translation_key="visibility",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="windgust",
        translation_key="windgust",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="precipitation",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="irradiance",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_average",
        translation_key="precipitation_forecast_average",
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
    ),
    SensorEntityDescription(
        key="precipitation_forecast_total",
        translation_key="precipitation_forecast_total",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlast24hour",
        translation_key="rainlast24hour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="rainlasthour",
        translation_key="rainlasthour",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="temperature_1d",
        translation_key="temperature_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_2d",
        translation_key="temperature_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_3d",
        translation_key="temperature_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_4d",
        translation_key="temperature_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="temperature_5d",
        translation_key="temperature_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_1d",
        translation_key="mintemp_1d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_2d",
        translation_key="mintemp_2d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_3d",
        translation_key="mintemp_3d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_4d",
        translation_key="mintemp_4d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="mintemp_5d",
        translation_key="mintemp_5d",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorEntityDescription(
        key="rain_1d",
        translation_key="rain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_2d",
        translation_key="rain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_3d",
        translation_key="rain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_4d",
        translation_key="rain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rain_5d",
        translation_key="rain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="minrain_1d",
        translation_key="minrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_2d",
        translation_key="minrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_3d",
        translation_key="minrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_4d",
        translation_key="minrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="minrain_5d",
        translation_key="minrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    # new in json api (>1.0.0):
    SensorEntityDescription(
        key="maxrain_1d",
        translation_key="maxrain_1d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_2d",
        translation_key="maxrain_2d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_3d",
        translation_key="maxrain_3d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_4d",
        translation_key="maxrain_4d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="maxrain_5d",
        translation_key="maxrain_5d",
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
    ),
    SensorEntityDescription(
        key="rainchance_1d",
        translation_key="rainchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_pouring,
    ),
    SensorEntityDescription(
        key="rainchance_2d",
        translation_key="rainchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_pouring,
    ),
    SensorEntityDescription(
        key="rainchance_3d",
        translation_key="rainchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_pouring,
    ),
    SensorEntityDescription(
        key="rainchance_4d",
        translation_key="rainchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_pouring,
    ),
    SensorEntityDescription(
        key="rainchance_5d",
        translation_key="rainchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_pouring,
    ),
    SensorEntityDescription(
        key="sunchance_1d",
        translation_key="sunchance_1d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_partly_cloudy,
    ),
    SensorEntityDescription(
        key="sunchance_2d",
        translation_key="sunchance_2d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_partly_cloudy,
    ),
    SensorEntityDescription(
        key="sunchance_3d",
        translation_key="sunchance_3d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_partly_cloudy,
    ),
    SensorEntityDescription(
        key="sunchance_4d",
        translation_key="sunchance_4d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_partly_cloudy,
    ),
    SensorEntityDescription(
        key="sunchance_5d",
        translation_key="sunchance_5d",
        native_unit_of_measurement=PERCENTAGE,
        icon=mdi_weather_partly_cloudy,
    ),
    SensorEntityDescription(
        key="windforce_1d",
        translation_key="windforce_1d",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="windforce_2d",
        translation_key="windforce_2d",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="windforce_3d",
        translation_key="windforce_3d",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="windforce_4d",
        translation_key="windforce_4d",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="windforce_5d",
        translation_key="windforce_5d",
        native_unit_of_measurement="Bft",
        icon=mdi_weather_windy,
    ),
    SensorEntityDescription(
        key="windspeed_1d",
        translation_key="windspeed_1d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_2d",
        translation_key="windspeed_2d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_3d",
        translation_key="windspeed_3d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_4d",
        translation_key="windspeed_4d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="windspeed_5d",
        translation_key="windspeed_5d",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.WIND_SPEED,
    ),
    SensorEntityDescription(
        key="winddirection_1d",
        translation_key="winddirection_1d",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="winddirection_2d",
        translation_key="winddirection_2d",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="winddirection_3d",
        translation_key="winddirection_3d",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="winddirection_4d",
        translation_key="winddirection_4d",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="winddirection_5d",
        translation_key="winddirection_5d",
        icon=mdi_compass_outline,
    ),
    SensorEntityDescription(
        key="windazimuth_1d",
        translation_key="windazimuth_1d",
        native_unit_of_measurement=DEGREE,
        icon=mdi_compass_outline,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_2d",
        translation_key="windazimuth_2d",
        native_unit_of_measurement=DEGREE,
        icon=mdi_compass_outline,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_3d",
        translation_key="windazimuth_3d",
        native_unit_of_measurement=DEGREE,
        icon=mdi_compass_outline,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_4d",
        translation_key="windazimuth_4d",
        native_unit_of_measurement=DEGREE,
        icon=mdi_compass_outline,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="windazimuth_5d",
        translation_key="windazimuth_5d",
        native_unit_of_measurement=DEGREE,
        icon=mdi_compass_outline,
        device_class=SensorDeviceClass.WIND_DIRECTION,
    ),
    SensorEntityDescription(
        key="condition_1d",
        translation_key="condition_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_2d",
        translation_key="condition_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_3d",
        translation_key="condition_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_4d",
        translation_key="condition_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="condition_5d",
        translation_key="condition_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditioncode_1d",
        translation_key="conditioncode_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_2d",
        translation_key="conditioncode_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_3d",
        translation_key="conditioncode_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_4d",
        translation_key="conditioncode_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditioncode_5d",
        translation_key="conditioncode_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_CONDITION_CODES,
    ),
    SensorEntityDescription(
        key="conditiondetailed_1d",
        translation_key="conditiondetailed_1d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_2d",
        translation_key="conditiondetailed_2d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_3d",
        translation_key="conditiondetailed_3d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_4d",
        translation_key="conditiondetailed_4d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditiondetailed_5d",
        translation_key="conditiondetailed_5d",
        device_class=SensorDeviceClass.ENUM,
        options=STATE_DETAILED_CONDITIONS,
    ),
    SensorEntityDescription(
        key="conditionexact_1d",
        translation_key="conditionexact_1d",
    ),
    SensorEntityDescription(
        key="conditionexact_2d",
        translation_key="conditionexact_2d",
    ),
    SensorEntityDescription(
        key="conditionexact_3d",
        translation_key="conditionexact_3d",
    ),
    SensorEntityDescription(
        key="conditionexact_4d",
        translation_key="conditionexact_4d",
    ),
    SensorEntityDescription(
        key="conditionexact_5d",
        translation_key="conditionexact_5d",
    ),
    SensorEntityDescription(
        key="symbol_1d",
        translation_key="symbol_1d",
    ),
    SensorEntityDescription(
        key="symbol_2d",
        translation_key="symbol_2d",
    ),
    SensorEntityDescription(
        key="symbol_3d",
        translation_key="symbol_3d",
    ),
    SensorEntityDescription(
        key="symbol_4d",
        translation_key="symbol_4d",
    ),
    SensorEntityDescription(
        key="symbol_5d",
        translation_key="symbol_5d",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BuienRadarConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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

    # create weather entities:
    entities = [
        BrSensor(config.get(CONF_NAME, "Buienradar"), coordinates, description)
        for description in SENSOR_TYPES
    ]

    # create weather data:
    data = BrData(hass, coordinates, timeframe, entities)
    entry.runtime_data[Platform.SENSOR] = data
    await data.async_update()

    async_add_entities(entities)


class BrSensor(SensorEntity):
    """Representation of a Buienradar sensor."""

    _attr_entity_registry_enabled_default = False
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self, client_name, coordinates, description: SensorEntityDescription
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._data: BrData | None = None
        self._measured = None
        self._attr_unique_id = (
            f"{coordinates[CONF_LATITUDE]:2.6f}{coordinates[CONF_LONGITUDE]:2.6f}"
            f"{description.key}"
        )

        # All continuous sensors should be forced to be updated
        self._attr_force_update = (
            description.key != SYMBOL and not description.key.startswith(CONDITION)
        )

        if description.key.startswith(PRECIPITATION_FORECAST):
            self._timeframe = None

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to hass."""
        if self._data is None:
            return
        self._update()

    @callback
    def data_updated(self, data: BrData):
        """Handle data update."""
        self._data = data
        if not self.hass:
            return
        self._update()

    def _update(self):
        """Update sensor data."""
        _LOGGER.debug("Updating sensor %s", self.entity_id)
        if self._load_data(self._data.data):
            self.async_write_ha_state()

    @callback

    # NEW private helper for forecast sensors
    def _load_forecast_data(self, data: dict[str, Any], sensor_type: str) -> bool:
        """Load data for a forecast sensor."""
        fcday = 0
        if sensor_type.endswith("_2d"):
            fcday = 1
        elif sensor_type.endswith("_3d"):
            fcday = 2
        elif sensor_type.endswith("_4d"):
            fcday = 3
        elif sensor_type.endswith("_5d"):
            fcday = 4

        try:
            forecast_data = data.get(FORECAST, [])[fcday]
        except (IndexError, TypeError):
            _LOGGER.warning("No forecast available for fcday=%s", fcday)
            return False

        if sensor_type.startswith((SYMBOL, CONDITION)):
            return self._update_condition_sensor(forecast_data.get(CONDITION), sensor_type)

        if sensor_type.startswith(WINDSPEED):
            wind_speed_ms = forecast_data.get(sensor_type[:-3])
            if wind_speed_ms is not None:
                self._attr_native_value = round(wind_speed_ms * 3.6, 1)
                return True
            return False

        self._attr_native_value = forecast_data.get(sensor_type[:-3])
        return True

    # NEW private helper for condition sensors
    def _update_condition_sensor(self, condition_data: dict[str, Any] | None, sensor_type: str) -> bool:
        """Update a weather symbol or condition sensor."""
        if not condition_data:
            return False

        new_state = None
        if sensor_type.startswith(SYMBOL):
            new_state = condition_data.get(EXACTNL)
        elif sensor_type.startswith("conditioncode"):
            new_state = condition_data.get(CONDCODE)
        elif sensor_type.startswith("conditiondetailed"):
            new_state = condition_data.get(DETAILED)
        elif sensor_type.startswith("conditionexact"):
            new_state = condition_data.get(EXACT)
        elif sensor_type.startswith(CONDITION):
            new_state = condition_data.get(CONDITION)

        img = condition_data.get(IMAGE)

        if new_state != self.state or img != self.entity_picture:
            self._attr_native_value = new_state
            self._attr_entity_picture = img
            return True
        return False

    # NEW private helper for precipitation forecast
    def _load_precipitation_forecast_data(self, data: dict[str, Any], sensor_type: str) -> bool:
        """Load data for a precipitation forecast sensor."""
        nested = data.get(PRECIPITATION_FORECAST, {})
        self._timeframe = nested.get(TIMEFRAME)
        self._attr_native_value = nested.get(sensor_type[len(PRECIPITATION_FORECAST) + 1 :])
        return True

    # NEW private helper for wind data
    def _load_wind_data(self, data: dict[str, Any], sensor_type: str) -> bool:
        """Load data for a wind sensor and convert units."""
        wind_speed_ms = data.get(sensor_type)
        if wind_speed_ms is not None:
            self._attr_native_value = round(wind_speed_ms * 3.6, 1)
            return True
        return False

    # NEW private helper for visibility data
    def _load_visibility_data(self, data: dict[str, Any], sensor_type: str) -> bool:
        """Load data for a visibility sensor and convert units."""
        visibility_m = data.get(sensor_type)
        if visibility_m is not None:
            self._attr_native_value = round(visibility_m / 1000, 1)
            return True
        return False

    # NEW private helper for all other sensor types
    def _load_default_sensor_data(self, data: dict[str, Any], sensor_type: str) -> bool:
        """Load data for a generic sensor."""
        self._attr_native_value = data.get(sensor_type)
        return True

    # This is the FINAL REFACTORED main function
    @callback
    def _load_data(self, data: dict[str, Any]) -> bool:
        """Load the sensor with relevant data."""
        if self._measured == data.get(MEASURED):
            return False

        self._measured = data.get(MEASURED)
        sensor_type = self.entity_description.key

        # Dispatcher mapping conditions to handler functions
        dispatcher = {
            lambda st: st.endswith(("_1d", "_2d", "_3d", "_4d", "_5d")): self._load_forecast_data,
            lambda st: st.startswith((SYMBOL, CONDITION)): self._update_condition_sensor,
            lambda st: st.startswith(PRECIPITATION_FORECAST): self._load_precipitation_forecast_data,
            lambda st: st in [WINDSPEED, WINDGUST]: self._load_wind_data,
            lambda st: st == VISIBILITY: self._load_visibility_data,
        }

        needs_update = False
        handler_found = False
        for condition, handler in dispatcher.items():
            if condition(sensor_type):
                needs_update = handler(data, sensor_type)
                handler_found = True
                break
        
        if not handler_found:
            needs_update = self._load_default_sensor_data(data, sensor_type)

        if needs_update:
            # This part is common logic, so it stays at the end
            result = {
                ATTR_ATTRIBUTION: data.get(ATTRIBUTION),
                STATIONNAME_LABEL: data.get(STATIONNAME),
            }
            if self._measured is not None:
                local_dt = dt_util.as_local(self._measured)
                result[MEASURED_LABEL] = local_dt.strftime("%c")

            if sensor_type.startswith(PRECIPITATION_FORECAST) and self._timeframe is not None:
                result[TIMEFRAME_LABEL] = f"{self._timeframe} min"
                
            self._attr_extra_state_attributes = result

        return needs_update