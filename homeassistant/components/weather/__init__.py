"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Final, TypedDict, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.temperature import display_temp as show_temp
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import (
    distance as distance_util,
    pressure as pressure_util,
    speed as speed_util,
    temperature as temperature_util,
)

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
ATTR_WEATHER_HUMIDITY = "humidity"
ATTR_WEATHER_OZONE = "ozone"
ATTR_WEATHER_PRESSURE = "pressure"
ATTR_WEATHER_TEMPERATURE = "temperature"
ATTR_WEATHER_VISIBILITY = "visibility"
ATTR_WEATHER_WIND_BEARING = "wind_bearing"
ATTR_WEATHER_WIND_SPEED = "wind_speed"

CONF_PRECIPITATION_UOM = "precipitation_unit_of_measurement"
CONF_PRESSURE_UOM = "pressure_unit_of_measurement"
CONF_TEMPERATURE_UOM = "temperature_unit_of_measurement"
CONF_VISIBILITY_UOM = "visibility_unit_of_measurement"
CONF_WIND_SPEED_UOM = "wind_speed_unit_of_measurement"

DOMAIN = "weather"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)

ROUNDING_PRECISION = 2

VALID_UNITS_PRESSURE: tuple[str, ...] = (
    PRESSURE_HPA,
    PRESSURE_MBAR,
    PRESSURE_INHG,
    PRESSURE_MMHG,
)
VALID_UNITS_TEMPERATURE: tuple[str, ...] = (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
VALID_UNITS_PRECIPITATION: tuple[str, ...] = (
    LENGTH_MILLIMETERS,
    LENGTH_INCHES,
)
VALID_UNITS_VISIBILITY: tuple[str, ...] = (
    LENGTH_KILOMETERS,
    LENGTH_MILES,
)
VALID_UNITS_SPEED: tuple[str, ...] = (
    SPEED_METERS_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
)

UNIT_CONVERSIONS: dict[str, Callable[[float, str, str], float]] = {
    CONF_PRESSURE_UOM: pressure_util.convert,
    CONF_TEMPERATURE_UOM: temperature_util.convert,
    CONF_VISIBILITY_UOM: distance_util.convert,
    CONF_PRECIPITATION_UOM: distance_util.convert,
    CONF_WIND_SPEED_UOM: speed_util.convert,
}

UNIT_RATIOS: dict[str, dict[str, float]] = {
    CONF_PRESSURE_UOM: pressure_util.UNIT_CONVERSION,
    CONF_TEMPERATURE_UOM: {
        TEMP_CELSIUS: 1.0,
        TEMP_FAHRENHEIT: 1.8,
    },
    CONF_VISIBILITY_UOM: distance_util.METERS_TO,
    CONF_PRECIPITATION_UOM: distance_util.METERS_TO,
    CONF_WIND_SPEED_UOM: speed_util.UNIT_CONVERSION,
}

VALID_UNITS: dict[str, tuple[str, ...]] = {
    CONF_PRESSURE_UOM: VALID_UNITS_PRESSURE,
    CONF_TEMPERATURE_UOM: VALID_UNITS_TEMPERATURE,
    CONF_VISIBILITY_UOM: VALID_UNITS_VISIBILITY,
    CONF_PRECIPITATION_UOM: VALID_UNITS_PRECIPITATION,
    CONF_WIND_SPEED_UOM: VALID_UNITS_SPEED,
}


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
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


@dataclass
class WeatherEntityDescription(EntityDescription):
    """A class that describes weather entities."""


class WeatherEntity(Entity):
    """ABC for weather data."""

    entity_description: WeatherEntityDescription
    _attr_condition: str | None
    _attr_forecast: list[Forecast] | None = None
    _attr_humidity: float | None = None
    _attr_ozone: float | None = None
    _attr_precision: float
    _attr_pressure: float | None = None
    _attr_pressure_unit: None = None  # Subclasses of WeatherEntity should not set this
    _attr_native_pressure_unit: str | None = None
    _attr_state: None = None
    _attr_temperature_unit: None = (
        None  # Subclasses of WeatherEntity should not set this
    )
    _attr_native_temperature_unit: str
    _attr_temperature: float | None
    _attr_visibility: float | None = None
    _attr_visibility_unit: None = (
        None  # Subclasses of WeatherEntity should not set this
    )
    _attr_native_visibility_unit: str | None = None
    _attr_precipitation_unit: None = (
        None  # Subclasses of WeatherEntity should not set this
    )
    _attr_native_precipitation_unit: str | None = None
    _attr_wind_bearing: float | str | None = None
    _attr_wind_speed: float | None = None
    _attr_wind_speed_unit: None = (
        None  # Subclasses of WeatherEntity should not set this
    )
    _attr_native_wind_speed_unit: str | None = None

    _weather_option_temperature_uom: str | None = None
    _weather_option_pressure_uom: str | None = None
    _weather_option_visibility_uom: str | None = None
    _weather_option_precipitation_uom: str | None = None
    _weather_option_wind_speed_uom: str | None = None

    @property
    def temperature(self) -> float | None:
        """Return the platform temperature in native units (i.e. not converted)."""
        return self._attr_temperature

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the native unit of measurement for temperature."""
        if hasattr(self, "_attr_native_temperature_unit"):
            return self._attr_native_temperature_unit
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement for temperature."""
        if self._weather_option_temperature_uom:
            return self._weather_option_temperature_uom

        return self.hass.config.units.temperature_unit

    @property
    def pressure(self) -> float | None:
        """Return the pressure in native units."""
        return self._attr_pressure

    @property
    def native_pressure_unit(self) -> str | None:
        """Return the native unit of measurement for pressure."""
        if hasattr(self, "_attr_native_pressure_unit"):
            return self._attr_native_pressure_unit
        return None

    @property
    def pressure_unit(self) -> str | None:
        """Return the unit of measurement for pressure."""
        if self._weather_option_pressure_uom:
            return self._weather_option_pressure_uom

        if self.hass.config.units.is_metric:
            return PRESSURE_HPA
        return PRESSURE_INHG

    @property
    def humidity(self) -> float | None:
        """Return the humidity in native units."""
        return self._attr_humidity

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        return self._attr_wind_speed

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the native unit of measurement for wind speed."""
        if hasattr(self, "_attr_native_wind_speed_unit"):
            return self._attr_native_wind_speed_unit
        return None

    @property
    def wind_speed_unit(self) -> str | None:
        """Return the unit of measurement for wind speed."""
        if self._weather_option_wind_speed_uom:
            return self._weather_option_wind_speed_uom

        if self.hass.config.units.is_metric:
            return SPEED_METERS_PER_SECOND
        return SPEED_MILES_PER_HOUR

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._attr_wind_bearing

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._attr_ozone

    @property
    def visibility(self) -> float | None:
        """Return the visibility in native units."""
        return self._attr_visibility

    @property
    def visibility_unit(self) -> str | None:
        """Return the native unit of measurement for visibility."""
        return self._attr_visibility_unit

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast in native units."""
        return self._attr_forecast

    @property
    def precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        return self._attr_precipitation_unit

    @property
    def precision(self) -> float:
        """Return the precision of the temperature value, after unit conversion."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        return (
            PRECISION_TENTHS
            if self.hass.config.units.temperature_unit == TEMP_CELSIUS
            else PRECISION_WHOLE
        )

    @final
    @property
    def state_attributes(self):
        """Return the state attributes, converted from native units to user-configured units."""
        data = {}
        if self.temperature is not None:
            data[ATTR_WEATHER_TEMPERATURE] = show_temp(
                self.hass,
                self.temperature,
                self.temperature_unit,
                self.precision,
            )

        if (humidity := self.humidity) is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

        if (ozone := self.ozone) is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        if (pressure := self.pressure) is not None:
            if (unit := self.pressure_unit) is not None:
                pressure = round(
                    self.hass.config.units.pressure(pressure, unit), ROUNDING_PRECISION
                )
            data[ATTR_WEATHER_PRESSURE] = pressure

        if (wind_bearing := self.wind_bearing) is not None:
            data[ATTR_WEATHER_WIND_BEARING] = wind_bearing

        if (wind_speed := self.wind_speed) is not None:
            if (unit := self.wind_speed_unit) is not None:
                wind_speed = round(
                    self.hass.config.units.wind_speed(wind_speed, unit),
                    ROUNDING_PRECISION,
                )
            data[ATTR_WEATHER_WIND_SPEED] = wind_speed

        if (visibility := self.visibility) is not None:
            if (unit := self.visibility_unit) is not None:
                visibility = round(
                    self.hass.config.units.length(visibility, unit), ROUNDING_PRECISION
                )
            data[ATTR_WEATHER_VISIBILITY] = visibility

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
                if (
                    native_pressure := forecast_entry.get(ATTR_FORECAST_PRESSURE)
                ) is not None:
                    if (unit := self.pressure_unit) is not None:
                        pressure = round(
                            self.hass.config.units.pressure(native_pressure, unit),
                            ROUNDING_PRECISION,
                        )
                        forecast_entry[ATTR_FORECAST_PRESSURE] = pressure
                if (
                    native_wind_speed := forecast_entry.get(ATTR_FORECAST_WIND_SPEED)
                ) is not None:
                    if (unit := self.wind_speed_unit) is not None:
                        wind_speed = round(
                            self.hass.config.units.wind_speed(native_wind_speed, unit),
                            ROUNDING_PRECISION,
                        )
                        forecast_entry[ATTR_FORECAST_WIND_SPEED] = wind_speed
                if (
                    native_precip := forecast_entry.get(ATTR_FORECAST_PRECIPITATION)
                ) is not None:
                    if (unit := self.precipitation_unit) is not None:
                        precipitation = round(
                            self.hass.config.units.accumulated_precipitation(
                                native_precip, unit
                            ),
                            ROUNDING_PRECISION,
                        )
                        forecast_entry[ATTR_FORECAST_PRECIPITATION] = precipitation

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

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        assert self.registry_entry
        weather_options = self.registry_entry.options.get(DOMAIN)
        if (
            weather_options
            and (custom_unit_temperature := weather_options.get(CONF_TEMPERATURE_UOM))
            and self.native_temperature_unit in VALID_UNITS[CONF_TEMPERATURE_UOM]
            and custom_unit_temperature in VALID_UNITS[CONF_TEMPERATURE_UOM]
        ):
            self._weather_option_temperature_uom = custom_unit_temperature
            return

        self._weather_option_temperature_uom = None
