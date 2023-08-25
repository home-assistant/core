"""Weather component that handles meteorological data for your location."""
from __future__ import annotations

import abc
from collections.abc import Callable, Iterable
from contextlib import suppress
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
import inspect
import logging
from typing import (
    Any,
    Final,
    Generic,
    Literal,
    Required,
    TypedDict,
    TypeVar,
    cast,
    final,
)

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PRECISION_HALVES,
    PRECISION_TENTHS,
    PRECISION_WHOLE,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.config_validation import (  # noqa: F401
    PLATFORM_SCHEMA,
    PLATFORM_SCHEMA_BASE,
)
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    TimestampDataUpdateCoordinator,
)
from homeassistant.util.dt import utcnow
from homeassistant.util.json import JsonValueType
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from .const import (  # noqa: F401
    ATTR_WEATHER_APPARENT_TEMPERATURE,
    ATTR_WEATHER_CLOUD_COVERAGE,
    ATTR_WEATHER_DEW_POINT,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_OZONE,
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_PRESSURE_UNIT,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_UV_INDEX,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_VISIBILITY_UNIT,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_GUST_SPEED,
    ATTR_WEATHER_WIND_SPEED,
    ATTR_WEATHER_WIND_SPEED_UNIT,
    DOMAIN,
    UNIT_CONVERSIONS,
    VALID_UNITS,
    WeatherEntityFeature,
)
from .websocket_api import async_setup as async_setup_ws_api

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
ATTR_FORECAST_IS_DAYTIME: Final = "is_daytime"
ATTR_FORECAST_CONDITION: Final = "condition"
ATTR_FORECAST_HUMIDITY: Final = "humidity"
ATTR_FORECAST_NATIVE_PRECIPITATION: Final = "native_precipitation"
ATTR_FORECAST_PRECIPITATION: Final = "precipitation"
ATTR_FORECAST_PRECIPITATION_PROBABILITY: Final = "precipitation_probability"
ATTR_FORECAST_NATIVE_PRESSURE: Final = "native_pressure"
ATTR_FORECAST_PRESSURE: Final = "pressure"
ATTR_FORECAST_NATIVE_APPARENT_TEMP: Final = "native_apparent_temperature"
ATTR_FORECAST_APPARENT_TEMP: Final = "apparent_temperature"
ATTR_FORECAST_NATIVE_TEMP: Final = "native_temperature"
ATTR_FORECAST_TEMP: Final = "temperature"
ATTR_FORECAST_NATIVE_TEMP_LOW: Final = "native_templow"
ATTR_FORECAST_TEMP_LOW: Final = "templow"
ATTR_FORECAST_TIME: Final = "datetime"
ATTR_FORECAST_WIND_BEARING: Final = "wind_bearing"
ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: Final = "native_wind_gust_speed"
ATTR_FORECAST_WIND_GUST_SPEED: Final = "wind_gust_speed"
ATTR_FORECAST_NATIVE_WIND_SPEED: Final = "native_wind_speed"
ATTR_FORECAST_WIND_SPEED: Final = "wind_speed"
ATTR_FORECAST_NATIVE_DEW_POINT: Final = "native_dew_point"
ATTR_FORECAST_DEW_POINT: Final = "dew_point"
ATTR_FORECAST_CLOUD_COVERAGE: Final = "cloud_coverage"
ATTR_FORECAST_UV_INDEX: Final = "uv_index"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

SCAN_INTERVAL = timedelta(seconds=30)

ROUNDING_PRECISION = 2

SERVICE_GET_FORECAST: Final = "get_forecast"

_ObservationUpdateCoordinatorT = TypeVar(
    "_ObservationUpdateCoordinatorT", bound="DataUpdateCoordinator[Any]"
)

# Note:
# Mypy bug https://github.com/python/mypy/issues/9424 prevents us from making the
# forecast cooordinators optional, bound=TimestampDataUpdateCoordinator[Any] | None

_DailyForecastUpdateCoordinatorT = TypeVar(
    "_DailyForecastUpdateCoordinatorT", bound="TimestampDataUpdateCoordinator[Any]"
)
_HourlyForecastUpdateCoordinatorT = TypeVar(
    "_HourlyForecastUpdateCoordinatorT", bound="TimestampDataUpdateCoordinator[Any]"
)
_TwiceDailyForecastUpdateCoordinatorT = TypeVar(
    "_TwiceDailyForecastUpdateCoordinatorT", bound="TimestampDataUpdateCoordinator[Any]"
)

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

    All attributes are in native units and old attributes kept
    for backwards compatibility.
    """

    condition: str | None
    datetime: Required[str]
    humidity: float | None
    precipitation_probability: int | None
    cloud_coverage: int | None
    native_precipitation: float | None
    precipitation: None
    native_pressure: float | None
    pressure: None
    native_temperature: float | None
    temperature: None
    native_templow: float | None
    templow: None
    native_apparent_temperature: float | None
    wind_bearing: float | str | None
    native_wind_gust_speed: float | None
    native_wind_speed: float | None
    wind_speed: None
    native_dew_point: float | None
    uv_index: float | None
    is_daytime: bool | None  # Mandatory to use with forecast_twice_daily


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the weather component."""
    component = hass.data[DOMAIN] = EntityComponent[WeatherEntity](
        _LOGGER, DOMAIN, hass, SCAN_INTERVAL
    )
    component.async_register_entity_service(
        SERVICE_GET_FORECAST,
        {vol.Required("type"): vol.In(("daily", "hourly", "twice_daily"))},
        async_get_forecast_service,
        required_features=[
            WeatherEntityFeature.FORECAST_DAILY,
            WeatherEntityFeature.FORECAST_HOURLY,
            WeatherEntityFeature.FORECAST_TWICE_DAILY,
        ],
        supports_response=SupportsResponse.ONLY,
    )
    async_setup_ws_api(hass)
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


class PostInitMeta(abc.ABCMeta):
    """Meta class which calls __post_init__ after __new__ and __init__."""

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Create an instance."""
        instance: PostInit = super().__call__(*args, **kwargs)
        instance.__post_init__(*args, **kwargs)
        return instance


class PostInit(metaclass=PostInitMeta):
    """Class which calls __post_init__ after __new__ and __init__."""

    @abc.abstractmethod
    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        """Finish initializing."""


class WeatherEntity(Entity, PostInit):
    """ABC for weather data."""

    entity_description: WeatherEntityDescription
    _attr_condition: str | None = None
    # _attr_forecast is deprecated, implement async_forecast_daily,
    # async_forecast_hourly or async_forecast_twice daily instead
    _attr_forecast: list[Forecast] | None = None
    _attr_humidity: float | None = None
    _attr_ozone: float | None = None
    _attr_cloud_coverage: int | None = None
    _attr_uv_index: float | None = None
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
    _attr_native_apparent_temperature: float | None = None
    _attr_native_temperature: float | None = None
    _attr_native_temperature_unit: str | None = None
    _attr_native_visibility: float | None = None
    _attr_native_visibility_unit: str | None = None
    _attr_native_precipitation_unit: str | None = None
    _attr_native_wind_gust_speed: float | None = None
    _attr_native_wind_speed: float | None = None
    _attr_native_wind_speed_unit: str | None = None
    _attr_native_dew_point: float | None = None

    _forecast_listeners: dict[
        Literal["daily", "hourly", "twice_daily"],
        list[Callable[[list[JsonValueType] | None], None]],
    ]

    _weather_option_temperature_unit: str | None = None
    _weather_option_pressure_unit: str | None = None
    _weather_option_visibility_unit: str | None = None
    _weather_option_precipitation_unit: str | None = None
    _weather_option_wind_speed_unit: str | None = None

    def __post_init__(self, *args: Any, **kwargs: Any) -> None:
        """Finish initializing."""
        self._forecast_listeners = {"daily": [], "hourly": [], "twice_daily": []}

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
                    (
                        "%s::%s is overriding deprecated methods on an instance of "
                        "WeatherEntity, this is not valid and will be unsupported "
                        "from Home Assistant 2023.1. Please %s"
                    ),
                    cls.__module__,
                    cls.__name__,
                    report_issue,
                )

    async def async_internal_added_to_hass(self) -> None:
        """Call when the weather entity is added to hass."""
        await super().async_internal_added_to_hass()
        if not self.registry_entry:
            return
        self.async_registry_entry_updated()

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature in native units."""
        return self._attr_native_temperature

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

    @property
    def native_dew_point(self) -> float | None:
        """Return the dew point temperature in native units."""
        return self._attr_native_dew_point

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
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            return UnitOfPressure.INHG
        return UnitOfPressure.HPA

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

    @property
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed in native units."""
        return self._attr_native_wind_gust_speed

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
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            return UnitOfSpeed.MILES_PER_HOUR
        return UnitOfSpeed.KILOMETERS_PER_HOUR

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

    @property
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        return self._attr_cloud_coverage

    @property
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self._attr_uv_index

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
        """Return the forecast in native units.

        Should not be overridden by integrations. Kept for backwards compatibility.
        """
        return self._attr_forecast

    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        raise NotImplementedError

    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        raise NotImplementedError

    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        raise NotImplementedError

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
            if self._temperature_unit == UnitOfTemperature.CELSIUS
            else PRECISION_WHOLE
        )

    @final
    @property
    def state_attributes(self) -> dict[str, Any]:  # noqa: C901
        """Return the state attributes, converted.

        Attributes are configured from native units to user-configured units.
        """
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

        if (apparent_temperature := self.native_apparent_temperature) is not None:
            from_unit = self.native_temperature_unit or self._default_temperature_unit
            to_unit = self._temperature_unit
            try:
                apparent_temperature_f = float(apparent_temperature)
                value_apparent_temp = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                    apparent_temperature_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_APPARENT_TEMPERATURE] = round_temperature(
                    value_apparent_temp, precision
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_APPARENT_TEMPERATURE] = apparent_temperature

        if (dew_point := self.native_dew_point) is not None:
            from_unit = self.native_temperature_unit or self._default_temperature_unit
            to_unit = self._temperature_unit
            try:
                dew_point_f = float(dew_point)
                value_dew_point = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                    dew_point_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_DEW_POINT] = round_temperature(
                    value_dew_point, precision
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_DEW_POINT] = dew_point

        data[ATTR_WEATHER_TEMPERATURE_UNIT] = self._temperature_unit

        if (humidity := self.humidity) is not None:
            data[ATTR_WEATHER_HUMIDITY] = round(humidity)

        if (ozone := self.ozone) is not None:
            data[ATTR_WEATHER_OZONE] = ozone

        if (cloud_coverage := self.cloud_coverage) is not None:
            data[ATTR_WEATHER_CLOUD_COVERAGE] = cloud_coverage

        if (uv_index := self.uv_index) is not None:
            data[ATTR_WEATHER_UV_INDEX] = uv_index

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

        if (wind_gust_speed := self.native_wind_gust_speed) is not None:
            from_unit = self.native_wind_speed_unit or self._default_wind_speed_unit
            to_unit = self._wind_speed_unit
            try:
                wind_gust_speed_f = float(wind_gust_speed)
                value_wind_gust_speed = UNIT_CONVERSIONS[ATTR_WEATHER_WIND_SPEED_UNIT](
                    wind_gust_speed_f, from_unit, to_unit
                )
                data[ATTR_WEATHER_WIND_GUST_SPEED] = round(
                    value_wind_gust_speed, ROUNDING_PRECISION
                )
            except (TypeError, ValueError):
                data[ATTR_WEATHER_WIND_GUST_SPEED] = wind_gust_speed

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

        if self.forecast:
            data[ATTR_FORECAST] = self._convert_forecast(self.forecast)

        return data

    @final
    def _convert_forecast(
        self, native_forecast_list: list[Forecast]
    ) -> list[JsonValueType]:
        """Convert a forecast in native units to the unit configured by the user."""
        converted_forecast_list: list[JsonValueType] = []
        precision = self.precision

        from_temp_unit = self.native_temperature_unit or self._default_temperature_unit
        to_temp_unit = self._temperature_unit

        for _forecast_entry in native_forecast_list:
            forecast_entry: dict[str, Any] = dict(_forecast_entry)

            temperature = forecast_entry.pop(
                ATTR_FORECAST_NATIVE_TEMP, forecast_entry.get(ATTR_FORECAST_TEMP)
            )

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
                forecast_apparent_temp := forecast_entry.pop(
                    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
                    forecast_entry.get(ATTR_FORECAST_NATIVE_APPARENT_TEMP),
                )
            ) is not None:
                with suppress(TypeError, ValueError):
                    forecast_apparent_temp = float(forecast_apparent_temp)
                    value_apparent_temp = UNIT_CONVERSIONS[
                        ATTR_WEATHER_TEMPERATURE_UNIT
                    ](
                        forecast_apparent_temp,
                        from_temp_unit,
                        to_temp_unit,
                    )

                    forecast_entry[ATTR_FORECAST_APPARENT_TEMP] = round_temperature(
                        value_apparent_temp, precision
                    )

            if (
                forecast_temp_low := forecast_entry.pop(
                    ATTR_FORECAST_NATIVE_TEMP_LOW,
                    forecast_entry.get(ATTR_FORECAST_TEMP_LOW),
                )
            ) is not None:
                with suppress(TypeError, ValueError):
                    forecast_temp_low_f = float(forecast_temp_low)
                    value_temp_low = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                        forecast_temp_low_f,
                        from_temp_unit,
                        to_temp_unit,
                    )

                    forecast_entry[ATTR_FORECAST_TEMP_LOW] = round_temperature(
                        value_temp_low, precision
                    )

            if (
                forecast_dew_point := forecast_entry.pop(
                    ATTR_FORECAST_NATIVE_DEW_POINT,
                    None,
                )
            ) is not None:
                with suppress(TypeError, ValueError):
                    forecast_dew_point_f = float(forecast_dew_point)
                    value_dew_point = UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                        forecast_dew_point_f,
                        from_temp_unit,
                        to_temp_unit,
                    )

                    forecast_entry[ATTR_FORECAST_DEW_POINT] = round_temperature(
                        value_dew_point, precision
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
                forecast_wind_gust_speed := forecast_entry.pop(
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
                    None,
                )
            ) is not None:
                from_wind_speed_unit = (
                    self.native_wind_speed_unit or self._default_wind_speed_unit
                )
                to_wind_speed_unit = self._wind_speed_unit
                with suppress(TypeError, ValueError):
                    forecast_wind_gust_speed_f = float(forecast_wind_gust_speed)
                    forecast_entry[ATTR_FORECAST_WIND_GUST_SPEED] = round(
                        UNIT_CONVERSIONS[ATTR_WEATHER_WIND_SPEED_UNIT](
                            forecast_wind_gust_speed_f,
                            from_wind_speed_unit,
                            to_wind_speed_unit,
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
                    self.native_precipitation_unit or self._default_precipitation_unit
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

            if (
                forecast_humidity := forecast_entry.pop(
                    ATTR_FORECAST_HUMIDITY,
                    None,
                )
            ) is not None:
                with suppress(TypeError, ValueError):
                    forecast_humidity_f = float(forecast_humidity)
                    forecast_entry[ATTR_FORECAST_HUMIDITY] = round(forecast_humidity_f)

            converted_forecast_list.append(forecast_entry)

        return converted_forecast_list

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

    @callback
    def _async_subscription_started(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
    ) -> None:
        """Start subscription to forecast_type."""
        return None

    @callback
    def _async_subscription_ended(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
    ) -> None:
        """End subscription to forecast_type."""
        return None

    @final
    @callback
    def async_subscribe_forecast(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
        forecast_listener: Callable[[list[JsonValueType] | None], None],
    ) -> CALLBACK_TYPE:
        """Subscribe to forecast updates.

        Called by websocket API.
        """
        subscription_started = not self._forecast_listeners[forecast_type]
        self._forecast_listeners[forecast_type].append(forecast_listener)
        if subscription_started:
            self._async_subscription_started(forecast_type)

        @callback
        def unsubscribe() -> None:
            self._forecast_listeners[forecast_type].remove(forecast_listener)
            if not self._forecast_listeners[forecast_type]:
                self._async_subscription_ended(forecast_type)

        return unsubscribe

    @final
    async def async_update_listeners(
        self, forecast_types: Iterable[Literal["daily", "hourly", "twice_daily"]] | None
    ) -> None:
        """Push updated forecast to all listeners."""
        if forecast_types is None:
            forecast_types = {"daily", "hourly", "twice_daily"}
        for forecast_type in forecast_types:
            if not self._forecast_listeners[forecast_type]:
                continue

            native_forecast_list: list[Forecast] | None = await getattr(
                self, f"async_forecast_{forecast_type}"
            )()

            if native_forecast_list is None:
                for listener in self._forecast_listeners[forecast_type]:
                    listener(None)
                continue

            if forecast_type == "twice_daily":
                for fc_twice_daily in native_forecast_list:
                    if fc_twice_daily.get(ATTR_FORECAST_IS_DAYTIME) is None:
                        raise ValueError(
                            "is_daytime mandatory attribute for forecast_twice_daily is missing"
                        )

            converted_forecast_list = self._convert_forecast(native_forecast_list)
            for listener in self._forecast_listeners[forecast_type]:
                listener(converted_forecast_list)


def raise_unsupported_forecast(entity_id: str, forecast_type: str) -> None:
    """Raise error on attempt to get an unsupported forecast."""
    raise HomeAssistantError(
        f"Weather entity '{entity_id}' does not support '{forecast_type}' forecast"
    )


async def async_get_forecast_service(
    weather: WeatherEntity, service_call: ServiceCall
) -> ServiceResponse:
    """Get weather forecast."""
    forecast_type = service_call.data["type"]
    supported_features = weather.supported_features or 0
    if forecast_type == "daily":
        if (supported_features & WeatherEntityFeature.FORECAST_DAILY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_daily()
    elif forecast_type == "hourly":
        if (supported_features & WeatherEntityFeature.FORECAST_HOURLY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_hourly()
    else:
        if (supported_features & WeatherEntityFeature.FORECAST_TWICE_DAILY) == 0:
            raise_unsupported_forecast(weather.entity_id, forecast_type)
        native_forecast_list = await weather.async_forecast_twice_daily()
    if native_forecast_list is None:
        converted_forecast_list = []
    else:
        # pylint: disable-next=protected-access
        converted_forecast_list = weather._convert_forecast(native_forecast_list)
    return {
        "forecast": converted_forecast_list,
    }


class CoordinatorWeatherEntity(
    CoordinatorEntity[_ObservationUpdateCoordinatorT],
    WeatherEntity,
    Generic[
        _ObservationUpdateCoordinatorT,
        _DailyForecastUpdateCoordinatorT,
        _HourlyForecastUpdateCoordinatorT,
        _TwiceDailyForecastUpdateCoordinatorT,
    ],
):
    """A class for weather entities using DataUpdateCoordinators."""

    def __init__(
        self,
        observation_coordinator: _ObservationUpdateCoordinatorT,
        *,
        context: Any = None,
        daily_coordinator: _DailyForecastUpdateCoordinatorT | None = None,
        hourly_coordinator: _DailyForecastUpdateCoordinatorT | None = None,
        twice_daily_coordinator: _DailyForecastUpdateCoordinatorT | None = None,
        daily_forecast_valid: timedelta | None = None,
        hourly_forecast_valid: timedelta | None = None,
        twice_daily_forecast_valid: timedelta | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(observation_coordinator, context)
        self.forecast_coordinators = {
            "daily": daily_coordinator,
            "hourly": hourly_coordinator,
            "twice_daily": twice_daily_coordinator,
        }
        self.forecast_valid = {
            "daily": daily_forecast_valid,
            "hourly": hourly_forecast_valid,
            "twice_daily": twice_daily_forecast_valid,
        }
        self.unsub_forecast: dict[str, Callable[[], None] | None] = {
            "daily": None,
            "hourly": None,
            "twice_daily": None,
        }

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(partial(self._remove_forecast_listener, "daily"))
        self.async_on_remove(partial(self._remove_forecast_listener, "hourly"))
        self.async_on_remove(partial(self._remove_forecast_listener, "twice_daily"))

    def _remove_forecast_listener(
        self, forecast_type: Literal["daily", "hourly", "twice_daily"]
    ) -> None:
        """Remove weather forecast listener."""
        if unsub_fn := self.unsub_forecast[forecast_type]:
            unsub_fn()
            self.unsub_forecast[forecast_type] = None

    @callback
    def _async_subscription_started(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
    ) -> None:
        """Start subscription to forecast_type."""
        if not (coordinator := self.forecast_coordinators[forecast_type]):
            return
        self.unsub_forecast[forecast_type] = coordinator.async_add_listener(
            partial(self._handle_forecast_update, forecast_type)
        )

    @callback
    def _handle_daily_forecast_coordinator_update(self) -> None:
        """Handle updated data from the daily forecast coordinator."""

    @callback
    def _handle_hourly_forecast_coordinator_update(self) -> None:
        """Handle updated data from the hourly forecast coordinator."""

    @callback
    def _handle_twice_daily_forecast_coordinator_update(self) -> None:
        """Handle updated data from the twice daily forecast coordinator."""

    @final
    @callback
    def _handle_forecast_update(
        self, forecast_type: Literal["daily", "hourly", "twice_daily"]
    ) -> None:
        """Update forecast data."""
        coordinator = self.forecast_coordinators[forecast_type]
        assert coordinator
        assert coordinator.config_entry is not None
        getattr(self, f"_handle_{forecast_type}_forecast_coordinator_update")()
        coordinator.config_entry.async_create_task(
            self.hass, self.async_update_listeners((forecast_type,))
        )

    @callback
    def _async_subscription_ended(
        self,
        forecast_type: Literal["daily", "hourly", "twice_daily"],
    ) -> None:
        """End subscription to forecast_type."""
        self._remove_forecast_listener(forecast_type)

    @final
    async def _async_refresh_forecast(
        self,
        coordinator: TimestampDataUpdateCoordinator[Any],
        forecast_valid_time: timedelta | None,
    ) -> bool:
        """Refresh stale forecast if needed."""
        if coordinator.update_interval is None:
            return True
        if forecast_valid_time is None:
            forecast_valid_time = coordinator.update_interval
        if (
            not (last_success_time := coordinator.last_update_success_time)
            or utcnow() - last_success_time >= coordinator.update_interval
        ):
            await coordinator.async_refresh()
        if (
            not (last_success_time := coordinator.last_update_success_time)
            or utcnow() - last_success_time >= forecast_valid_time
        ):
            return False
        return True

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        raise NotImplementedError

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        raise NotImplementedError

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        raise NotImplementedError

    @final
    async def _async_forecast(
        self, forecast_type: Literal["daily", "hourly", "twice_daily"]
    ) -> list[Forecast] | None:
        """Return the forecast in native units."""
        coordinator = self.forecast_coordinators[forecast_type]
        if coordinator and not await self._async_refresh_forecast(
            coordinator, self.forecast_valid[forecast_type]
        ):
            return None
        return cast(
            list[Forecast] | None, getattr(self, f"_async_forecast_{forecast_type}")()
        )

    @final
    async def async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return await self._async_forecast("daily")

    @final
    async def async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        return await self._async_forecast("hourly")

    @final
    async def async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        return await self._async_forecast("twice_daily")


class SingleCoordinatorWeatherEntity(
    CoordinatorWeatherEntity[
        _ObservationUpdateCoordinatorT,
        TimestampDataUpdateCoordinator[None],
        TimestampDataUpdateCoordinator[None],
        TimestampDataUpdateCoordinator[None],
    ],
):
    """A class for weather entities using a single DataUpdateCoordinators.

    This class is added as a convenience because:
    - Deriving from CoordinatorWeatherEntity requires specifying all type parameters
    until we upgrade to Python 3.12 which supports defaults
    - Mypy bug https://github.com/python/mypy/issues/9424 prevents us from making the
    forecast cooordinator type vars optional
    """

    def __init__(
        self,
        coordinator: _ObservationUpdateCoordinatorT,
        context: Any = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator, context=context)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        assert self.coordinator.config_entry
        self.coordinator.config_entry.async_create_task(
            self.hass, self.async_update_listeners(None)
        )
