"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final, TypedDict, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, PRECISION_WHOLE, TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp

# mypy: allow-untyped-defs, no-check-untyped-defs

_LOGGER = logging.getLogger(__name__)

ATTR_CONDITION_CLASS = "condition_class"
ATTR_CONDITION_CLEAR_NIGHT = "clear-night"
ATTR_CONDITION_CLOUDY = "cloudy"
ATTR_CONDITION_EXCEPTIONAL = "exceptional"
ATTR_CONDITION_FOG = "fog"
ATTR_CONDITION_HAIL = "hail"
ATTR_CONDITION_LIGHTNING = "lightning"
ATTR_CONDITION_LIGHTNING_RAINY = "lightning-rainy"
ATTR_CONDITION_PARTLYCLOUDY = "partlycloudy"
ATTR_CONDITION_POURING = "pouring"
ATTR_CONDITION_RAINY = "rainy"
ATTR_CONDITION_SNOWY = "snowy"
ATTR_CONDITION_SNOWY_RAINY = "snowy-rainy"
ATTR_CONDITION_SUNNY = "sunny"
ATTR_CONDITION_WINDY = "windy"
ATTR_CONDITION_WINDY_VARIANT = "windy-variant"
ATTR_FORECAST = "forecast"
ATTR_FORECAST_CONDITION: Final = "condition"
ATTR_FORECAST_PRECIPITATION: Final = "precipitation"
ATTR_FORECAST_PRECIPITATION_PROBABILITY: Final = "precipitation_probability"
ATTR_FORECAST_PRESSURE: Final = "pressure"
ATTR_FORECAST_TEMP: Final = "temperature"
ATTR_FORECAST_TEMP_LOW: Final = "templow"
ATTR_FORECAST_TIME: Final = "datetime"
ATTR_FORECAST_WIND_BEARING: Final = "wind_bearing"
ATTR_FORECAST_WIND_SPEED: Final = "wind_speed"
ATTR_WEATHER_ATTRIBUTION = "attribution"
ATTR_WEATHER_HUMIDITY = "humidity"
ATTR_WEATHER_OZONE = "ozone"
ATTR_WEATHER_PRESSURE = "pressure"
ATTR_WEATHER_TEMPERATURE = "temperature"
ATTR_WEATHER_VISIBILITY = "visibility"
ATTR_WEATHER_WIND_BEARING = "wind_bearing"
ATTR_WEATHER_WIND_SPEED = "wind_speed"

DOMAIN = "weather"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)


class Forecast(TypedDict, total=False):
    """Typed weather forecast dict."""

    condition: str | None
    datetime: str
    precipitation_probability: int | None
    precipitation: float | None
    pressure: float | None
    temperature: float | None
    templow: float | None
    wind_bearing: float | str | None
    wind_speed: float | None


async def async_setup(hass, config):
    """Set up the weather component."""
    component = hass.data[DOMAIN] = EntityComponent(
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent = hass.data[DOMAIN]
    return await component.async_unload_entry(entry)


class WeatherEntity(Entity):
    """ABC for weather data."""

    _attr_attribution: str | None = None
    _attr_condition: str | None
    _attr_forecast: list[Forecast] | None = None
    _attr_humidity: float | None = None
    _attr_ozone: float | None = None
    _attr_precision: float
    _attr_pressure: float | None = None
    _attr_state: None = None
    _attr_temperature_unit: str
    _attr_temperature: float | None
    _attr_visibility: float | None = None
    _attr_wind_bearing: float | str | None = None
    _attr_wind_speed: float | None = None

    @property
    def temperature(self) -> float | None:
        """Return the platform temperature."""
        return self._attr_temperature

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return self._attr_temperature_unit

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        return self._attr_pressure

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self._attr_humidity

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self._attr_wind_speed

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._attr_wind_bearing

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._attr_ozone

    @property
    def attribution(self) -> str | None:
        """Return the attribution."""
        return self._attr_attribution

    @property
    def visibility(self) -> float | None:
        """Return the visibility."""
        return self._attr_visibility

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast."""
        return self._attr_forecast

    @property
    def precision(self) -> float:
        """Return the precision of the temperature value."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        return (
            PRECISION_TENTHS
            if self.temperature_unit == TEMP_CELSIUS
            else PRECISION_WHOLE
        )

    @final
    @property
    def state_attributes(self):
        """Return the state attributes."""
        data = {}
        if self.temperature is not None:
            data[ATTR_WEATHER_TEMPERATURE] = show_temp(
                self.hass, self.temperature, self.temperature_unit, self.precision
            )

        humidity = self.humidity
        if humidity is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

        ozone = self.ozone
        if ozone is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        pressure = self.pressure
        if pressure is not None:
            data[ATTR_WEATHER_PRESSURE] = pressure

        wind_bearing = self.wind_bearing
        if wind_bearing is not None:
            data[ATTR_WEATHER_WIND_BEARING] = wind_bearing

        wind_speed = self.wind_speed
        if wind_speed is not None:
            data[ATTR_WEATHER_WIND_SPEED] = wind_speed

        visibility = self.visibility
        if visibility is not None:
            data[ATTR_WEATHER_VISIBILITY] = visibility

        attribution = self.attribution
        if attribution is not None:
            data[ATTR_WEATHER_ATTRIBUTION] = attribution

        if self.forecast is not None:
            forecast = []
            for forecast_entry in self.forecast:
                forecast_entry = dict(forecast_entry)
                forecast_entry[ATTR_FORECAST_TEMP] = show_temp(
                    self.hass,
                    forecast_entry[ATTR_FORECAST_TEMP],
                    self.temperature_unit,
                    self.precision,
                )
                if ATTR_FORECAST_TEMP_LOW in forecast_entry:
                    forecast_entry[ATTR_FORECAST_TEMP_LOW] = show_temp(
                        self.hass,
                        forecast_entry[ATTR_FORECAST_TEMP_LOW],
                        self.temperature_unit,
                        self.precision,
                    )
                forecast.append(forecast_entry)

            data[ATTR_FORECAST] = forecast

        return data

    @property
    @final
    def state(self) -> str | None:
        """Return the current state."""
        return self.condition

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self._attr_condition
