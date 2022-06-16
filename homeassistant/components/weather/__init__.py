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
ATTR_WEATHER_PRESSURE_UNIT = "pressure_unit"
ATTR_WEATHER_TEMPERATURE = "temperature"
ATTR_WEATHER_TEMPERATURE_UNIT = "temperature_unit"
ATTR_WEATHER_VISIBILITY = "visibility"
ATTR_WEATHER_VISIBILITY_UNIT = "visibility_unit"
ATTR_WEATHER_WIND_BEARING = "wind_bearing"
ATTR_WEATHER_WIND_SPEED = "wind_speed"
ATTR_WEATHER_WIND_SPEED_UNIT = "wind_speed_unit"
ATTR_WEATHER_PRECIPITATION_UNIT = "precipitation_unit"

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
    _attr_pressure_unit: str | None = None
    _attr_state: None = None
    _attr_temperature_unit: str | None = None
    _attr_visibility_unit: str | None = None
    _attr_precipitation_unit: str | None = None
    _attr_wind_bearing: float | str | None = None
    _attr_wind_speed_unit: str | None = None

    _attr_native_pressure: float | None = None
    _attr_native_pressure_unit: str | None = None
    _attr_native_temperature: float
    _attr_native_temperature_unit: str
    _attr_native_visibility: float | None = None
    _attr_native_visibility_unit: str | None = None
    _attr_native_precipitation: float | None = None
    _attr_native_precipitation_unit: str | None = None
    _attr_native_wind_speed: float | None = None
    _attr_native_wind_speed_unit: str | None = None

    _weather_option_temperature_uom: str | None = None
    _weather_option_pressure_uom: str | None = None
    _weather_option_visibility_uom: str | None = None
    _weather_option_precipitation_uom: str | None = None
    _weather_option_wind_speed_uom: str | None = None

    _override_temperature: bool = False
    _override_pressure: bool = False
    _override_visibility: bool = False
    _override_precipitation: bool = False
    _override_wind_speed: bool = False

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Post initialisation processing."""
        super().__init_subclass__(**kwargs)
        _reported = False
        for method in (
            "temperature",
            "temperature_unit",
            "_attr_temperature",
            "_attr_temperature_unit",
            "pressure",
            "pressure_unit",
            "_attr_pressure",
            "_attr_pressure_unit",
            "wind_speed",
            "wind_speed_unit",
            "_attr_wind_speed",
            "_attr_wind_speed_unit",
            "visibility",
            "visibility_unit",
            "_attr_visibility",
            "_attr_visibility_unit",
            "precipitation_unit",
            "_attr_precipitation_unit",
        ):
            if method in cls.__dict__:
                if "temperature" in method:
                    WeatherEntity._override_temperature = True
                if "pressure" in method:
                    WeatherEntity._override_pressure = True
                if "wind_speed" in method:
                    WeatherEntity._override_wind_speed = True
                if "visibility" in method:
                    WeatherEntity._override_visibility = True
                if "precipitation" in method:
                    WeatherEntity._override_precipitation = True
                module = inspect.getmodule(cls)
                if _reported is False:
                    _reported = True
                    if (
                        module
                        and module.__file__
                        and "custom_components" in module.__file__
                    ):
                        report_issue = "report it to the custom component author."
                    else:
                        report_issue = (
                            "create a bug report at "
                            "https://github.com/home-assistant/core/issues?q=is%3Aopen+is%3Aissue"
                        )
                    _LOGGER.warning(
                        "%s::%s is overriding deprecated methods on an instance of "
                        "WeatherEntity, this is not valid and will be unsupported "
                        "from Home Assistant 2022.10. Please %s",
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

    @property
    def native_temperature(self) -> float:
        """Return the platform temperature in native units (i.e. not converted)."""
        if self._override_temperature:
            if hasattr(self, "_attr_temperature"):
                return self._attr_temperature  # type: ignore[no-any-return, attr-defined]
            if hasattr(self, "temperature"):
                return self.temperature  # type: ignore[no-any-return, attr-defined]
        return self._attr_native_temperature

    @property
    def native_temperature_unit(self) -> str | None:
        """Return the native unit of measurement for temperature."""
        if self._override_temperature:
            if hasattr(self, "_attr_temperature_unit"):
                return self._attr_temperature_unit
            if hasattr(self, "temperature"):
                return self.temperature_unit
        if hasattr(self, "_attr_native_temperature_unit"):
            return self._attr_native_temperature_unit
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement for temperature."""
        if weather_option_temperature_uom := self._weather_option_temperature_uom:
            return weather_option_temperature_uom

        return self.native_temperature_unit  # type: ignore[return-value]

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure in native units."""
        if self._override_pressure:
            if hasattr(self, "_attr_pressure"):
                return self._attr_pressure  # type: ignore[no-any-return, attr-defined]
            if hasattr(self, "pressure"):
                return self.pressure  # type: ignore[no-any-return, attr-defined]
        return self._attr_native_pressure

    @property
    def native_pressure_unit(self) -> str | None:
        """Return the native unit of measurement for pressure."""
        if self._override_pressure:
            if hasattr(self, "_attr_pressure_unit"):
                return self._attr_pressure_unit
            if hasattr(self, "pressure_unit"):
                return self.pressure_unit
        if hasattr(self, "_attr_native_pressure_unit"):
            return self._attr_native_pressure_unit
        return None

    @property
    def pressure_unit(self) -> str | None:
        """Return the unit of measurement for pressure."""
        if (native_pressure_unit := self.native_pressure_unit) is None:
            return None

        if weather_option_pressure_uom := self._weather_option_pressure_uom:
            return weather_option_pressure_uom

        return native_pressure_unit

    @property
    def humidity(self) -> float | None:
        """Return the humidity in native units."""
        return self._attr_humidity

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        if self._override_wind_speed:
            if hasattr(self, "_attr_wind_speed"):
                return self._attr_wind_speed  # type: ignore[no-any-return, attr-defined]
            if hasattr(self, "wind_speed"):
                return self.wind_speed  # type: ignore[no-any-return, attr-defined]
        return self._attr_native_wind_speed

    @property
    def native_wind_speed_unit(self) -> str | None:
        """Return the native unit of measurement for wind speed."""
        if self._override_wind_speed:
            if hasattr(self, "_attr_wind_speed_unit"):
                return self._attr_wind_speed_unit
            if hasattr(self, "wind_speed_unit"):
                return self.wind_speed_unit
        if hasattr(self, "_attr_native_wind_speed_unit"):
            return self._attr_native_wind_speed_unit
        return None

    @property
    def wind_speed_unit(self) -> str | None:
        """Return the unit of measurement for wind speed."""
        if (native_wind_speed_unit := self.native_wind_speed_unit) is None:
            return None

        if weather_option_wind_speed_uom := self._weather_option_wind_speed_uom:
            return weather_option_wind_speed_uom

        return native_wind_speed_unit

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self._attr_wind_bearing

    @property
    def ozone(self) -> float | None:
        """Return the ozone level."""
        return self._attr_ozone

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility in native units."""
        if self._override_visibility:
            if hasattr(self, "_attr_visibility"):
                return self._attr_visibility  # type: ignore[no-any-return, attr-defined]
            if hasattr(self, "visibility"):
                return self.visibility  # type: ignore[no-any-return, attr-defined]
        return self._attr_native_visibility

    @property
    def native_visibility_unit(self) -> str | None:
        """Return the native unit of measurement for visibility."""
        if self._override_visibility:
            if hasattr(self, "_attr_visibility_unit"):
                return self._attr_visibility_unit
            if hasattr(self, "visibility_unit"):
                return self.visibility_unit
        if hasattr(self, "_attr_native_visibility_unit"):
            return self._attr_native_visibility_unit
        return None

    @property
    def visibility_unit(self) -> str | None:
        """Return the unit of measurement for visibility."""
        if (native_visibility_unit := self.native_visibility_unit) is None:
            return None

        if weather_option_visibility_uom := self._weather_option_visibility_uom:
            return weather_option_visibility_uom

        return native_visibility_unit

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast in native units."""
        return self._attr_forecast

    @property
    def native_precipitation_unit(self) -> str | None:
        """Return the native unit of measurement for accumulated precipitation."""
        if self._override_precipitation:
            if hasattr(self, "_attr_precipitation_unit"):
                return self._attr_precipitation_unit
            if hasattr(self, "precipitation_unit"):
                return self.precipitation_unit
        if hasattr(self, "_attr_native_precipitation_unit"):
            return self._attr_native_precipitation_unit
        return None

    @property
    def precipitation_unit(self) -> str | None:
        """Return the unit of measurement for precipitation."""
        if (native_precipitation_unit := self.native_precipitation_unit) is None:
            return None

        if weather_option_precipitation_uom := self._weather_option_precipitation_uom:
            return weather_option_precipitation_uom

        return native_precipitation_unit

    @property
    def precision(self) -> float:
        """Return the precision of the temperature value, after unit conversion."""
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
        """Return the state attributes, converted from native units to user-configured units."""
        data = {}

        precision_str = str(self.precision)
        precision = (
            len(precision_str) - precision_str.index(".") - 1
            if "." in precision_str
            else 0
        )

        if (
            (temperature := self.native_temperature) is not None
            and (native_temp_unit := self.native_temperature_unit) is not None
            and (temp_unit := self.temperature_unit) is not None
        ):
            with suppress(ValueError):
                temperature_f = float(temperature)
                value_temp = UNIT_CONVERSIONS[CONF_TEMPERATURE_UOM](
                    temperature_f, native_temp_unit, temp_unit
                )
                data[ATTR_WEATHER_TEMPERATURE] = (
                    round(value_temp)
                    if precision == 0
                    else round(value_temp, precision)
                )
                data[ATTR_WEATHER_TEMPERATURE_UNIT] = temp_unit

        if (humidity := self.humidity) is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

        if (ozone := self.ozone) is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        if (
            (pressure := self.native_pressure) is not None
            and (pressure_unit := self.pressure_unit) is not None
            and (native_pressure_unit := self.native_pressure_unit) is not None
        ):
            with suppress(ValueError):
                pressure_f = float(pressure)
                value_pressure = UNIT_CONVERSIONS[CONF_PRESSURE_UOM](
                    pressure_f, native_pressure_unit, pressure_unit
                )
                data[ATTR_WEATHER_PRESSURE] = round(value_pressure, ROUNDING_PRECISION)
                data[ATTR_WEATHER_PRESSURE_UNIT] = pressure_unit

        if (wind_bearing := self.wind_bearing) is not None:
            data[ATTR_WEATHER_WIND_BEARING] = wind_bearing

        if (
            (wind_speed := self.native_wind_speed) is not None
            and (wind_speed_unit := self.wind_speed_unit) is not None
            and (native_wind_speed_unit := self.native_wind_speed_unit) is not None
        ):
            with suppress(ValueError):
                wind_speed_f = float(wind_speed)
                value_wind_speed = UNIT_CONVERSIONS[CONF_WIND_SPEED_UOM](
                    wind_speed_f, native_wind_speed_unit, wind_speed_unit
                )
                data[ATTR_WEATHER_WIND_SPEED] = round(
                    value_wind_speed, ROUNDING_PRECISION
                )
                data[ATTR_WEATHER_WIND_SPEED_UNIT] = wind_speed_unit

        if (
            (visibility := self.native_visibility) is not None
            and (visibility_unit := self.visibility_unit) is not None
            and (native_visibility_unit := self.native_visibility_unit) is not None
        ):
            with suppress(ValueError):
                visibility_f = float(visibility)
                value_visibility = UNIT_CONVERSIONS[CONF_VISIBILITY_UOM](
                    visibility_f, native_visibility_unit, visibility_unit
                )
                data[ATTR_WEATHER_VISIBILITY] = round(
                    value_visibility, ROUNDING_PRECISION
                )
                data[ATTR_WEATHER_VISIBILITY_UNIT] = visibility_unit

        if self.forecast is not None:
            forecast = []
            for forecast_entry in self.forecast:
                forecast_entry_new = {}
                forecast_entry = dict(forecast_entry)
                temperature = forecast_entry[ATTR_FORECAST_TEMP]

                if (
                    self.temperature_unit is not None
                    and self.native_temperature_unit is not None
                ):
                    with suppress(ValueError):
                        value_temp = UNIT_CONVERSIONS[CONF_TEMPERATURE_UOM](
                            temperature,
                            self.native_temperature_unit,
                            self.temperature_unit,
                        )
                        forecast_entry_new[ATTR_FORECAST_TEMP] = (
                            round(value_temp)
                            if precision == 0
                            else round(value_temp, precision)
                        )
                else:
                    forecast_entry_new[ATTR_FORECAST_TEMP] = temperature

                if temp_low := forecast_entry.get(ATTR_FORECAST_TEMP_LOW):
                    if (
                        self.temperature_unit is not None
                        and self.native_temperature_unit is not None
                    ):
                        with suppress(ValueError):
                            forecast_entry_new[ATTR_FORECAST_TEMP_LOW] = round(
                                UNIT_CONVERSIONS[CONF_TEMPERATURE_UOM](
                                    temp_low,
                                    self.native_temperature_unit,
                                    self.temperature_unit,
                                ),
                                ROUNDING_PRECISION,
                            )
                    else:
                        forecast_entry_new[ATTR_FORECAST_TEMP_LOW] = temp_low

                if pressure := forecast_entry.get(ATTR_FORECAST_PRESSURE):
                    if (
                        self.pressure_unit is not None
                        and self.native_pressure_unit is not None
                    ):
                        with suppress(ValueError):
                            forecast_entry_new[ATTR_FORECAST_PRESSURE] = round(
                                UNIT_CONVERSIONS[CONF_PRESSURE_UOM](
                                    pressure,
                                    self.native_pressure_unit,
                                    self.pressure_unit,
                                ),
                                ROUNDING_PRECISION,
                            )
                    else:
                        forecast_entry_new[ATTR_FORECAST_PRESSURE] = pressure

                if wind_speed := forecast_entry.get(ATTR_FORECAST_WIND_SPEED):
                    if (
                        self.wind_speed_unit is not None
                        and self.native_wind_speed_unit is not None
                    ):
                        with suppress(ValueError):
                            forecast_entry_new[ATTR_FORECAST_WIND_SPEED] = round(
                                UNIT_CONVERSIONS[CONF_WIND_SPEED_UOM](
                                    wind_speed,
                                    self.native_wind_speed_unit,
                                    self.wind_speed_unit,
                                ),
                                ROUNDING_PRECISION,
                            )
                    else:
                        forecast_entry_new[ATTR_FORECAST_WIND_SPEED] = wind_speed

                if precipitation := forecast_entry.get(ATTR_FORECAST_PRECIPITATION):
                    if (
                        self.precipitation_unit is not None
                        and self.native_precipitation_unit is not None
                    ):
                        with suppress(ValueError):
                            forecast_entry_new[ATTR_FORECAST_PRECIPITATION] = round(
                                UNIT_CONVERSIONS[CONF_PRECIPITATION_UOM](
                                    precipitation,
                                    self.native_precipitation_unit,
                                    self.precipitation_unit,
                                ),
                                ROUNDING_PRECISION,
                            )
                    else:
                        forecast_entry_new[ATTR_FORECAST_PRECIPITATION] = precipitation

                forecast.append({**forecast_entry, **forecast_entry_new})

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
        self._weather_option_temperature_uom = None
        self._weather_option_pressure_uom = None
        self._weather_option_precipitation_uom = None
        self._weather_option_wind_speed_uom = None
        self._weather_option_visibility_uom = None
        if weather_options := self.registry_entry.options.get(DOMAIN):
            if (
                (custom_unit_temperature := weather_options.get(CONF_TEMPERATURE_UOM))
                and custom_unit_temperature in VALID_UNITS[CONF_TEMPERATURE_UOM]
                and self.native_temperature_unit in VALID_UNITS[CONF_TEMPERATURE_UOM]
            ):
                self._weather_option_temperature_uom = custom_unit_temperature
            if (
                (custom_unit_pressure := weather_options.get(CONF_PRESSURE_UOM))
                and custom_unit_pressure in VALID_UNITS[CONF_PRESSURE_UOM]
                and self.native_pressure_unit in VALID_UNITS[CONF_PRESSURE_UOM]
            ):
                self._weather_option_pressure_uom = custom_unit_pressure
            if (
                (
                    custom_unit_precipitation := weather_options.get(
                        CONF_PRECIPITATION_UOM
                    )
                )
                and custom_unit_precipitation in VALID_UNITS[CONF_PRECIPITATION_UOM]
                and self.native_precipitation_unit
                in VALID_UNITS[CONF_PRECIPITATION_UOM]
            ):
                self._weather_option_precipitation_uom = custom_unit_precipitation
            if (
                (custom_unit_wind_speed := weather_options.get(CONF_WIND_SPEED_UOM))
                and custom_unit_wind_speed in VALID_UNITS[CONF_WIND_SPEED_UOM]
                and self.native_wind_speed_unit in VALID_UNITS[CONF_WIND_SPEED_UOM]
            ):
                self._weather_option_wind_speed_uom = custom_unit_wind_speed
            if (
                (custom_unit_visibility := weather_options.get(CONF_VISIBILITY_UOM))
                and custom_unit_visibility in VALID_UNITS[CONF_VISIBILITY_UOM]
                and self.native_visibility_unit in VALID_UNITS[CONF_VISIBILITY_UOM]
            ):
                self._weather_option_visibility_uom = custom_unit_visibility
