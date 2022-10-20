"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
import inspect
import logging
from typing import Any, Final, TypedDict, final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    LENGTH_INCHES,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
    LENGTH_MILLIMETERS,
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_MBAR,
    PRESSURE_MMHG,
    SPEED_FEET_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
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
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)
from homeassistant.util.unit_system import METRIC_SYSTEM

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
ATTR_FORECAST_NATIVE_PRECIPITATION: Final = "native_precipitation"
ATTR_FORECAST_PRECIPITATION: Final = "precipitation"
ATTR_FORECAST_PRECIPITATION_PROBABILITY: Final = "precipitation_probability"
ATTR_FORECAST_NATIVE_PRESSURE: Final = "native_pressure"
ATTR_FORECAST_PRESSURE: Final = "pressure"
ATTR_FORECAST_NATIVE_TEMP: Final = "native_temperature"
ATTR_FORECAST_TEMP: Final = "temperature"
ATTR_FORECAST_NATIVE_TEMP_LOW: Final = "native_templow"
ATTR_FORECAST_TEMP_LOW: Final = "templow"
ATTR_FORECAST_TIME: Final = "datetime"
ATTR_FORECAST_WIND_BEARING: Final = "wind_bearing"
ATTR_FORECAST_NATIVE_WIND_SPEED: Final = "native_wind_speed"
ATTR_FORECAST_WIND_SPEED: Final = "wind_speed"
ATTR_WEATHER_HUMIDITY = "humidity"
ATTR_WEATHER_OZONE = "ozone"
ATTR_WEATHER_PRESSURE = "pressure"
ATTR_WEATHER_PRESSURE_UNIT = "pressure_unit"
ATTR_WEATHER_TEMPERATURE = "temperature"
ATTR_WEATHER_TEMPERATURE_UNIT = "temperature_unit"
ATTR_WEATHER_VISIBILITY = "visibility"
ATTR_WEATHER_VISIBILITY_UNIT = "visibility_unit"
ATTR_WEATHER_WIND_BEARING = "wind_bearing"
ATTR_WEATHER_WIND_SPEED = "wind_speed"
ATTR_WEATHER_WIND_SPEED_UNIT = "wind_speed_unit"
ATTR_WEATHER_PRECIPITATION_UNIT = "precipitation_unit"

DOMAIN = "weather"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)

ROUNDING_PRECISION = 2

VALID_UNITS_PRESSURE: set[str] = {
    PRESSURE_HPA,
    PRESSURE_MBAR,
    PRESSURE_INHG,
    PRESSURE_MMHG,
}
VALID_UNITS_TEMPERATURE: set[str] = {
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
}
VALID_UNITS_PRECIPITATION: set[str] = {
    LENGTH_MILLIMETERS,
    LENGTH_INCHES,
}
VALID_UNITS_VISIBILITY: set[str] = {
    LENGTH_KILOMETERS,
    LENGTH_MILES,
}
VALID_UNITS_WIND_SPEED: set[str] = {
    SPEED_FEET_PER_SECOND,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_KNOTS,
    SPEED_METERS_PER_SECOND,
    SPEED_MILES_PER_HOUR,
}

UNIT_CONVERSIONS: dict[str, Callable[[float, str, str], float]] = {
    ATTR_WEATHER_PRESSURE_UNIT: PressureConverter.convert,
    ATTR_WEATHER_TEMPERATURE_UNIT: TemperatureConverter.convert,
    ATTR_WEATHER_VISIBILITY_UNIT: DistanceConverter.convert,
    ATTR_WEATHER_PRECIPITATION_UNIT: DistanceConverter.convert,
    ATTR_WEATHER_WIND_SPEED_UNIT: SpeedConverter.convert,
}

VALID_UNITS: dict[str, set[str]] = {
    ATTR_WEATHER_PRESSURE_UNIT: VALID_UNITS_PRESSURE,
    ATTR_WEATHER_TEMPERATURE_UNIT: VALID_UNITS_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY_UNIT: VALID_UNITS_VISIBILITY,
    ATTR_WEATHER_PRECIPITATION_UNIT: VALID_UNITS_PRECIPITATION,
    ATTR_WEATHER_WIND_SPEED_UNIT: VALID_UNITS_WIND_SPEED,
}

# mypy: disallow-any-generics


def round_temperature(temperature: float | None, precision: float) -> float | None:
    """Convert temperature into preferred precision for display."""
    if temperature is None:
        return None

    # Round in the units appropriate
    if precision == PRECISION_HALVES:
        temperature = round(temperature * 2) / 2.0
    elif precision == PRECISION_TENTHS:
        temperature = round(temperature, 1)
    # Integer as a fall back (PRECISION_WHOLE)
    else:
        temperature = round(temperature)

    return temperature


class Forecast(TypedDict, total=False):
    """Typed weather forecast dict.

    All attributes are in native units and old attributes kept for backwards compatibility.
    """

    condition: str | None
    datetime: str
    precipitation_probability: int | None
    native_precipitation: float | None
    precipitation: None
    native_pressure: float | None
    pressure: None
    native_temperature: float | None
    temperature: None
    native_templow: float | None
    templow: None
    wind_bearing: float | str | None
    native_wind_speed: float | None
    wind_speed: None


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the weather component."""
    component = hass.data[DOMAIN] = EntityComponent[WeatherEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    await component.async_setup(config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    component: EntityComponent[WeatherEntity] = hass.data[DOMAIN]
    return await component.async_setup_entry(entry)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    component: EntityComponent[WeatherEntity] = hass.data[DOMAIN]
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
    _attr_pressure: None = (
        None  # Provide backwards compatibility. Use _attr_native_pressure
    )
    _attr_pressure_unit: None = (
        None  # Provide backwards compatibility. Use _attr_native_pressure_unit
    )
    _attr_state: None = None
    _attr_temperature: None = (
        None  # Provide backwards compatibility. Use _attr_native_temperature
    )
    _attr_temperature_unit: None = (
        None  # Provide backwards compatibility. Use _attr_native_temperature_unit
    )
    _attr_visibility: None = (
        None  # Provide backwards compatibility. Use _attr_native_visibility
    )
    _attr_visibility_unit: None = (
        None  # Provide backwards compatibility. Use _attr_native_visibility_unit
    )
    _attr_precipitation_unit: None = (
        None  # Provide backwards compatibility. Use _attr_native_precipitation_unit
    )
    _attr_wind_bearing: float | str | None = None
    _attr_wind_speed: None = (
        None  # Provide backwards compatibility. Use _attr_native_wind_speed
    )
    _attr_wind_speed_unit: None = (
        None  # Provide backwards compatibility. Use _attr_native_wind_speed_unit
    )

    _attr_native_pressure: float | None = None
    _attr_native_pressure_unit: str | None = None
    _attr_native_temperature: float | None = None
    _attr_native_temperature_unit: str | None = None
    _attr_native_visibility: float | None = None
    _attr_native_visibility_unit: str | None = None
    _attr_native_precipitation_unit: str | None = None
    _attr_native_wind_speed: float | None = None
    _attr_native_wind_speed_unit: str | None = None

    _weather_option_temperature_unit: str | None = None
    _weather_option_pressure_unit: str | None = None
    _weather_option_visibility_unit: str | None = None
    _weather_option_precipitation_unit: str | None = None
    _weather_option_wind_speed_unit: str | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        _reported = False
        if any(
            method in cls.__dict__
            for method in (
                "_attr_temperature",
                "temperature",
                "_attr_temperature_unit",
                "temperature_unit",
                "_attr_pressure",
                "pressure",
                "_attr_pressure_unit",
                "pressure_unit",
                "_attr_wind_speed",
                "wind_speed",
                "_attr_wind_speed_unit",
                "wind_speed_unit",
                "_attr_visibility",
                "visibility",
                "_attr_visibility_unit",
                "visibility_unit",
                "_attr_precipitation_unit",
                "precipitation_unit",
            )
        ):
            if _reported is False:
                module = inspect.getmodule(cls)
                _reported = True
                if (
                    module
                    and module.__file__
                    and "custom_components" in module.__file__
                ):
                    report_issue = "report it to the custom integration author."
                else:
                    report_issue = (
                        "create a bug report at "
                        "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
                    )
                _LOGGER.warning(
                    "%s::%s is overriding deprecated methods on an instance of "
                    "WeatherEntity, this is not valid and will be unsupported "
                    "from Home Assistant 2023.1. Please %s",
                    cls.__module__,
                    cls.__name__,
                    report_issue,
                )

    async def async_internal_added_to_hass(self) -> None:
        """Call when the sensor entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self.async_registry_entry_updated()

    @final
    @property
    def temperature(self) -> float | None:
        """Return the temperature for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_temperature

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature in native units."""
        if (temperature := self.temperature) is not None:
            return temperature

        return self._attr_native_temperature

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the native unit of measurement for temperature."""
        if (temperature_unit := self.temperature_unit) is not None:
            return temperature_unit

        return self._attr_native_temperature_unit

    @final
    @property
    def temperature_unit(self) -> str | None:
        """Return the temperature unit for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_temperature_unit

    @final
    @property
    def _default_temperature_unit(self) -> str:
        """Return the default unit of measurement for temperature.

        Should not be set by integrations.
        """
        return self.hass.config.units.temperature_unit

    @final
    @property
    def _temperature_unit(self) -> str:
        """Return the converted unit of measurement for temperature.

        Should not be set by integrations.
        """
        if (
            weather_option_temperature_unit := self._weather_option_temperature_unit
        ) is not None:
            return weather_option_temperature_unit

        return self._default_temperature_unit

    @final
    @property
    def pressure(self) -> float | None:
        """Return the pressure for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_pressure

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure in native units."""
        if (pressure := self.pressure) is not None:
            return pressure

        return self._attr_native_pressure

    @property
    def native_pressure_unit(self) -> str | None:
        """Return the native unit of measurement for pressure."""
        if (pressure_unit := self.pressure_unit) is not None:
            return pressure_unit

        return self._attr_native_pressure_unit

    @final
    @property
    def pressure_unit(self) -> str | None:
        """Return the pressure unit for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_pressure_unit

    @final
    @property
    def _default_pressure_unit(self) -> str:
        """Return the default unit of measurement for pressure.

        Should not be set by integrations.
        """
        return (
            PRESSURE_HPA if self.hass.config.units is METRIC_SYSTEM else PRESSURE_INHG
        )

    @final
    @property
    def _pressure_unit(self) -> str:
        """Return the converted unit of measurement for pressure.

        Should not be set by integrations.
        """
        if (
            weather_option_pressure_unit := self._weather_option_pressure_unit
        ) is not None:
            return weather_option_pressure_unit

        return self._default_pressure_unit

    @property
    def humidity(self) -> float | None:
        """Return the humidity in native units."""
        return self._attr_humidity

    @final
    @property
    def wind_speed(self) -> float | None:
        """Return the wind_speed for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_wind_speed

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        if (wind_speed := self.wind_speed) is not None:
            return wind_speed

        return self._attr_native_wind_speed

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the native unit of measurement for wind speed."""
        if (wind_speed_unit := self.wind_speed_unit) is not None:
            return wind_speed_unit

        return self._attr_native_wind_speed_unit

    @final
    @property
    def wind_speed_unit(self) -> str | None:
        """Return the wind_speed unit for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_wind_speed_unit

    @final
    @property
    def _default_wind_speed_unit(self) -> str:
        """Return the default unit of measurement for wind speed.

        Should not be set by integrations.
        """
        return (
            SPEED_KILOMETERS_PER_HOUR
            if self.hass.config.units is METRIC_SYSTEM
            else SPEED_MILES_PER_HOUR
        )

    @final
    @property
    def _wind_speed_unit(self) -> str:
        """Return the converted unit of measurement for wind speed.

        Should not be set by integrations.
        """
        if (
            weather_option_wind_speed_unit := self._weather_option_wind_speed_unit
        ) is not None:
            return weather_option_wind_speed_unit

        return self._default_wind_speed_unit

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._attr_wind_bearing

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._attr_ozone

    @final
    @property
    def visibility(self) -> float | None:
        """Return the visibility for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_visibility

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility in native units."""
        if (visibility := self.visibility) is not None:
            return visibility

        return self._attr_native_visibility

    @property
    def native_visibility_unit(self) -> str | None:
        """Return the native unit of measurement for visibility."""
        if (visibility_unit := self.visibility_unit) is not None:
            return visibility_unit

        return self._attr_native_visibility_unit

    @final
    @property
    def visibility_unit(self) -> str | None:
        """Return the visibility unit for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_visibility_unit

    @final
    @property
    def _default_visibility_unit(self) -> str:
        """Return the default unit of measurement for visibility.

        Should not be set by integrations.
        """
        return self.hass.config.units.length_unit

    @final
    @property
    def _visibility_unit(self) -> str:
        """Return the converted unit of measurement for visibility.

        Should not be set by integrations.
        """
        if (
            weather_option_visibility_unit := self._weather_option_visibility_unit
        ) is not None:
            return weather_option_visibility_unit

        return self._default_visibility_unit

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast in native units."""
        return self._attr_forecast

    @property
    def native_precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        if (precipitation_unit := self.precipitation_unit) is not None:
            return precipitation_unit

        return self._attr_native_precipitation_unit

    @final
    @property
    def precipitation_unit(self) -> str | None:
        """Return the precipitation unit for backward compatibility.

        Should not be set by integrations.
        """
        return self._attr_precipitation_unit

    @final
    @property
    def _default_precipitation_unit(self) -> str:
        """Return the default unit of measurement for precipitation.

        Should not be set by integrations.
        """
        return self.hass.config.units.accumulated_precipitation_unit

    @final
    @property
    def _precipitation_unit(self) -> str:
        """Return the converted unit of measurement for precipitation.

        Should not be set by integrations.
        """
        if (
            weather_option_precipitation_unit := self._weather_option_precipitation_unit
        ) is not None:
            return weather_option_precipitation_unit

        return self._default_precipitation_unit

    @property
    def precision(self) -> float:
        """Return the precision of the temperature value, after unit conversion."""
        if hasattr(self, "_attr_precision"):
            return self._attr_precision
        return (
            PRECISION_TENTHS
            if self._temperature_unit == TEMP_CELSIUS
            else PRECISION_WHOLE
        )

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:
        """Return the state attributes, converted from native units to user-configured units."""
        data: dict[str, Any] = {}

        precision = self.precision

        if (temperature := self.native_temperature) is not None:
            from_unit = self.native_temperature_unit or self._default_temperature_unit
            to_unit = self._temperature_unit
            try:
                temperature_f = float(temperature)
                value_temp = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                    temperature_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_TEMPERATURE] = round_temperature(
                    value_temp, precision
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_TEMPERATURE] = temperature

        data[ATTR_WEATHER_TEMPERATURE_UNIT] = self._temperature_unit

        if (humidity := self.humidity) is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

        if (ozone := self.ozone) is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        if (pressure := self.native_pressure) is not None:
            from_unit = self.native_pressure_unit or self._default_pressure_unit
            to_unit = self._pressure_unit
            try:
                pressure_f = float(pressure)
                value_pressure = UNIT_CONVERSIONS[ATTR_WEATHER_PRESSURE_UNIT](
                    pressure_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_PRESSURE] = round(value_pressure, ROUNDING_PRECISION)
            except (TypeError, ValueError):
                data[ATTR_WEATHER_PRESSURE] = pressure

        data[ATTR_WEATHER_PRESSURE_UNIT] = self._pressure_unit

        if (wind_bearing := self.wind_bearing) is not None:
            data[ATTR_WEATHER_WIND_BEARING] = wind_bearing

        if (wind_speed := self.native_wind_speed) is not None:
            from_unit = self.native_wind_speed_unit or self._default_wind_speed_unit
            to_unit = self._wind_speed_unit
            try:
                wind_speed_f = float(wind_speed)
                value_wind_speed = UNIT_CONVERSIONS[ATTR_WEATHER_WIND_SPEED_UNIT](
                    wind_speed_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_WIND_SPEED] = round(
                    value_wind_speed, ROUNDING_PRECISION
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_WIND_SPEED] = wind_speed

        data[ATTR_WEATHER_WIND_SPEED_UNIT] = self._wind_speed_unit

        if (visibility := self.native_visibility) is not None:
            from_unit = self.native_visibility_unit or self._default_visibility_unit
            to_unit = self._visibility_unit
            try:
                visibility_f = float(visibility)
                value_visibility = UNIT_CONVERSIONS[ATTR_WEATHER_VISIBILITY_UNIT](
                    visibility_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_VISIBILITY] = round(
                    value_visibility, ROUNDING_PRECISION
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_VISIBILITY] = visibility

        data[ATTR_WEATHER_VISIBILITY_UNIT] = self._visibility_unit
        data[ATTR_WEATHER_PRECIPITATION_UNIT] = self._precipitation_unit

        if self.forecast is not None:
            forecast: list[dict[str, Any]] = []
            for existing_forecast_entry in self.forecast:
                forecast_entry: dict[str, Any] = dict(existing_forecast_entry)

                temperature = forecast_entry.pop(
                    ATTR_FORECAST_NATIVE_TEMP, forecast_entry.get(ATTR_FORECAST_TEMP)
                )

                from_temp_unit = (
                    self.native_temperature_unit or self._default_temperature_unit
                )
                to_temp_unit = self._temperature_unit

                if temperature is None:
                    forecast_entry[ATTR_FORECAST_TEMP] = None
                else:
                    with suppress(TypeError, ValueError):
                        temperature_f = float(temperature)
                        value_temp = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                            temperature_f,
                            from_temp_unit,
                            to_temp_unit,
                        )
                        forecast_entry[ATTR_FORECAST_TEMP] = round_temperature(
                            value_temp, precision
                        )

                if (
                    forecast_temp_low := forecast_entry.pop(
                        ATTR_FORECAST_NATIVE_TEMP_LOW,
                        forecast_entry.get(ATTR_FORECAST_TEMP_LOW),
                    )
                ) is not None:
                    with suppress(TypeError, ValueError):
                        forecast_temp_low_f = float(forecast_temp_low)
                        value_temp_low = UNIT_CONVERSIONS[
                            ATTR_WEATHER_TEMPERATURE_UNIT
                        ](
                            forecast_temp_low_f,
                            from_temp_unit,
                            to_temp_unit,
                        )

                        forecast_entry[ATTR_FORECAST_TEMP_LOW] = round_temperature(
                            value_temp_low, precision
                        )

                if (
                    forecast_pressure := forecast_entry.pop(
                        ATTR_FORECAST_NATIVE_PRESSURE,
                        forecast_entry.get(ATTR_FORECAST_PRESSURE),
                    )
                ) is not None:
                    from_pressure_unit = (
                        self.native_pressure_unit or self._default_pressure_unit
                    )
                    to_pressure_unit = self._pressure_unit
                    with suppress(TypeError, ValueError):
                        forecast_pressure_f = float(forecast_pressure)
                        forecast_entry[ATTR_FORECAST_PRESSURE] = round(
                            UNIT_CONVERSIONS[ATTR_WEATHER_PRESSURE_UNIT](
                                forecast_pressure_f,
                                from_pressure_unit,
                                to_pressure_unit,
                            ),
                            ROUNDING_PRECISION,
                        )

                if (
                    forecast_wind_speed := forecast_entry.pop(
                        ATTR_FORECAST_NATIVE_WIND_SPEED,
                        forecast_entry.get(ATTR_FORECAST_WIND_SPEED),
                    )
                ) is not None:
                    from_wind_speed_unit = (
                        self.native_wind_speed_unit or self._default_wind_speed_unit
                    )
                    to_wind_speed_unit = self._wind_speed_unit
                    with suppress(TypeError, ValueError):
                        forecast_wind_speed_f = float(forecast_wind_speed)
                        forecast_entry[ATTR_FORECAST_WIND_SPEED] = round(
                            UNIT_CONVERSIONS[ATTR_WEATHER_WIND_SPEED_UNIT](
                                forecast_wind_speed_f,
                                from_wind_speed_unit,
                                to_wind_speed_unit,
                            ),
                            ROUNDING_PRECISION,
                        )

                if (
                    forecast_precipitation := forecast_entry.pop(
                        ATTR_FORECAST_NATIVE_PRECIPITATION,
                        forecast_entry.get(ATTR_FORECAST_PRECIPITATION),
                    )
                ) is not None:
                    from_precipitation_unit = (
                        self.native_precipitation_unit
                        or self._default_precipitation_unit
                    )
                    to_precipitation_unit = self._precipitation_unit
                    with suppress(TypeError, ValueError):
                        forecast_precipitation_f = float(forecast_precipitation)
                        forecast_entry[ATTR_FORECAST_PRECIPITATION] = round(
                            UNIT_CONVERSIONS[ATTR_WEATHER_PRECIPITATION_UNIT](
                                forecast_precipitation_f,
                                from_precipitation_unit,
                                to_precipitation_unit,
                            ),
                            ROUNDING_PRECISION,
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

    @callback
    def async_registry_entry_updated(self) -> None:
        """Run when the entity registry entry has been updated."""
        assert self.registry_entry
        self._weather_option_temperature_unit = None
        self._weather_option_pressure_unit = None
        self._weather_option_precipitation_unit = None
        self._weather_option_wind_speed_unit = None
        self._weather_option_visibility_unit = None
        if weather_options := self.registry_entry.options.get(DOMAIN):
            if (
                custom_unit_temperature := weather_options.get(
                    ATTR_WEATHER_TEMPERATURE_UNIT
                )
            ) and custom_unit_temperature in VALID_UNITS[ATTR_WEATHER_TEMPERATURE_UNIT]:
                self._weather_option_temperature_unit = custom_unit_temperature
            if (
                custom_unit_pressure := weather_options.get(ATTR_WEATHER_PRESSURE_UNIT)
            ) and custom_unit_pressure in VALID_UNITS[ATTR_WEATHER_PRESSURE_UNIT]:
                self._weather_option_pressure_unit = custom_unit_pressure
            if (
                custom_unit_precipitation := weather_options.get(
                    ATTR_WEATHER_PRECIPITATION_UNIT
                )
            ) and custom_unit_precipitation in VALID_UNITS[
                ATTR_WEATHER_PRECIPITATION_UNIT
            ]:
                self._weather_option_precipitation_unit = custom_unit_precipitation
            if (
                custom_unit_wind_speed := weather_options.get(
                    ATTR_WEATHER_WIND_SPEED_UNIT
                )
            ) and custom_unit_wind_speed in VALID_UNITS[ATTR_WEATHER_WIND_SPEED_UNIT]:
                self._weather_option_wind_speed_unit = custom_unit_wind_speed
            if (
                custom_unit_visibility := weather_options.get(
                    ATTR_WEATHER_VISIBILITY_UNIT
                )
            ) and custom_unit_visibility in VALID_UNITS[ATTR_WEATHER_VISIBILITY_UNIT]:
                self._weather_option_visibility_unit = custom_unit_visibility
