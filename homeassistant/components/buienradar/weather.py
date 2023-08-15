"""Support for Buienradar.nl weather service."""
import logging

from buienradar.constants import (
    CONDCODE,
    CONDITION,
    DATETIME,
    MAX_TEMP,
    MIN_TEMP,
    RAIN,
    WINDAZIMUTH,
    WINDSPEED,
)

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    Platform,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

# Reuse data and API logic from the sensor implementation
from .const import DEFAULT_TIMEFRAME, DOMAIN
from .util import BrData

_LOGGER = logging.getLogger(__name__)

CONF_FORECAST = "forecast"

DATA_CONDITION = "buienradar_condition"

CONDITION_CLASSES = {
    ATTR_CONDITION_CLOUDY: ("c", "p"),
    ATTR_CONDITION_FOG: ("d", "n"),
    ATTR_CONDITION_HAIL: (),
    ATTR_CONDITION_LIGHTNING: ("g",),
    ATTR_CONDITION_LIGHTNING_RAINY: ("s",),
    ATTR_CONDITION_PARTLYCLOUDY: (
        "b",
        "j",
        "o",
        "r",
    ),
    ATTR_CONDITION_POURING: ("l", "q"),
    ATTR_CONDITION_RAINY: ("f", "h", "k", "m"),
    ATTR_CONDITION_SNOWY: ("u", "i", "v", "t"),
    ATTR_CONDITION_SNOWY_RAINY: ("w",),
    ATTR_CONDITION_SUNNY: ("a",),
    ATTR_CONDITION_WINDY: (),
    ATTR_CONDITION_WINDY_VARIANT: (),
    ATTR_CONDITION_EXCEPTIONAL: (),
}
CONDITION_MAP = {
    cond_code: cond_ha
    for cond_ha, cond_codes in CONDITION_CLASSES.items()
    for cond_code in cond_codes
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the buienradar platform."""
    config = entry.data

    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)

    if None in (latitude, longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return

    coordinates = {CONF_LATITUDE: float(latitude), CONF_LONGITUDE: float(longitude)}

    # create weather entity:
    _LOGGER.debug("Initializing buienradar weather: coordinates %s", coordinates)
    entities = [BrWeather(config, coordinates)]

    # create weather data:
    data = BrData(hass, coordinates, DEFAULT_TIMEFRAME, entities)
    hass.data[DOMAIN][entry.entry_id][Platform.WEATHER] = data
    await data.async_update()

    async_add_entities(entities)


class BrWeather(WeatherEntity):
    """Representation of a weather condition."""

    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_should_poll = False

    def __init__(self, config, coordinates):
        """Initialize the platform with a data instance and station name."""
        self._stationname = config.get(CONF_NAME, "Buienradar")
        self._attr_name = self._stationname or f"BR {'(unknown station)'}"

        self._attr_condition = None
        self._attr_unique_id = "{:2.6f}{:2.6f}".format(
            coordinates[CONF_LATITUDE], coordinates[CONF_LONGITUDE]
        )

    @callback
    def data_updated(self, data: BrData) -> None:
        """Update data."""
        self._attr_attribution = data.attribution
        self._attr_condition = self._calc_condition(data)
        self._attr_forecast = self._calc_forecast(data)
        self._attr_humidity = data.humidity
        self._attr_name = (
            self._stationname or f"BR {data.stationname or '(unknown station)'}"
        )
        self._attr_native_pressure = data.pressure
        self._attr_native_temperature = data.temperature
        self._attr_native_visibility = data.visibility
        self._attr_native_wind_speed = data.wind_speed
        self._attr_wind_bearing = data.wind_bearing

        if not self.hass:
            return
        self.async_write_ha_state()

    def _calc_condition(self, data: BrData):
        """Return the current condition."""
        if data.condition and (ccode := data.condition.get(CONDCODE)):
            return CONDITION_MAP.get(ccode)
        return None

    def _calc_forecast(self, data: BrData):
        """Return the forecast array."""
        fcdata_out = []

        if not data.forecast:
            return None

        for data_in in data.forecast:
            # remap keys from external library to
            # keys understood by the weather component:
            condcode = data_in.get(CONDITION, {}).get(CONDCODE)
            data_out = {
                ATTR_FORECAST_TIME: data_in.get(DATETIME).isoformat(),
                ATTR_FORECAST_CONDITION: CONDITION_MAP.get(condcode),
                ATTR_FORECAST_NATIVE_TEMP_LOW: data_in.get(MIN_TEMP),
                ATTR_FORECAST_NATIVE_TEMP: data_in.get(MAX_TEMP),
                ATTR_FORECAST_NATIVE_PRECIPITATION: data_in.get(RAIN),
                ATTR_FORECAST_WIND_BEARING: data_in.get(WINDAZIMUTH),
                ATTR_FORECAST_NATIVE_WIND_SPEED: data_in.get(WINDSPEED),
            }

            fcdata_out.append(data_out)

        return fcdata_out
