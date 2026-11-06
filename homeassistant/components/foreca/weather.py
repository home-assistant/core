"""Weather platform for the Foreca integration."""

from typing import override

from pyforeca import DailyForecast, HourlyForecast

from homeassistant.components.weather import (
    ATTR_WEATHER_PRECIPITATION_UNIT,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    ATTR_WEATHER_VISIBILITY_UNIT,
    UNIT_CONVERSIONS,
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.util.json import JsonValueType

from .const import symbol_to_condition
from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator
from .entity import ForecaEntity

PARALLEL_UPDATES = 0

_CONFIDENCE = {"g": "good", "y": "normal", "o": "low"}
_ROUNDING_PRECISION = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a Foreca weather entity for every configured location."""
    for subentry_id, coordinator in entry.runtime_data.items():
        async_add_entities(
            [ForecaWeather(coordinator, subentry_id)],
            config_subentry_id=subentry_id,
        )


def _daily_to_forecast(day: DailyForecast) -> Forecast | None:
    """Convert a Foreca daily forecast to a Home Assistant forecast."""
    # The API dates a day rather than timing it, so anchor it to the start of
    # that day where Home Assistant is: midnight UTC lands on the day before
    # for anyone west of it.
    if (date := dt_util.parse_date(day.date or "")) is None:
        return None
    return Forecast(
        datetime=dt_util.start_of_local_day(date).isoformat(),
        condition=symbol_to_condition(day.symbol),
        native_temperature=day.max_temp,
        native_templow=day.min_temp,
        native_apparent_temperature=day.max_feels_like_temp,
        native_precipitation=day.precip_accum,
        precipitation_probability=day.precip_prob,
        native_wind_speed=day.max_wind_speed,
        native_wind_gust_speed=day.max_wind_gust,
        wind_bearing=day.wind_dir,
        native_pressure=day.pressure,
        native_dew_point=day.max_dew_point,
        cloud_coverage=day.cloudiness,
        uv_index=day.uv_index,
    )


def _hourly_to_forecast(hour: HourlyForecast) -> Forecast | None:
    """Convert a Foreca hourly forecast to a Home Assistant forecast."""
    if (timestamp := dt_util.parse_datetime(hour.time or "")) is None:
        return None
    return Forecast(
        datetime=timestamp.isoformat(),
        condition=symbol_to_condition(hour.symbol),
        native_temperature=hour.temperature,
        native_apparent_temperature=hour.feels_like_temp,
        native_precipitation=hour.precip_accum,
        precipitation_probability=hour.precip_prob,
        native_wind_speed=hour.wind_speed,
        native_wind_gust_speed=hour.wind_gust,
        wind_bearing=hour.wind_dir,
        humidity=hour.rel_humidity,
        cloud_coverage=hour.cloudiness,
        native_pressure=hour.pressure,
        native_dew_point=hour.dew_point,
        uv_index=hour.uv_index,
    )


class ForecaWeather(
    SingleCoordinatorWeatherEntity[ForecaUpdateCoordinator], ForecaEntity
):
    """Define a Foreca weather entity."""

    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: ForecaUpdateCoordinator, subentry_id: str) -> None:
        """Initialize the weather entity."""
        super().__init__(coordinator)
        self._attr_unique_id = subentry_id
        self._attr_device_info = coordinator.device_info

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        return symbol_to_condition(self.coordinator.data.current.symbol)

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.current.temperature

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data.current.feels_like_temp

    @property
    @override
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self.coordinator.data.current.dew_point

    @property
    @override
    def humidity(self) -> float | None:
        """Return the humidity."""
        return self.coordinator.data.current.rel_humidity

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        return self.coordinator.data.current.pressure

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.current.wind_speed

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        return self.coordinator.data.current.wind_gust

    @property
    @override
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        return self.coordinator.data.current.wind_dir

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self.coordinator.data.current.visibility

    @property
    @override
    def cloud_coverage(self) -> float | None:
        """Return the cloud coverage."""
        return self.coordinator.data.current.cloudiness

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the UV index."""
        return self.coordinator.data.current.uv_index

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast."""
        return [
            forecast
            for day in self.coordinator.data.daily
            if (forecast := _daily_to_forecast(day)) is not None
        ]

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast."""
        return [
            forecast
            for hour in self.coordinator.data.hourly
            if (forecast := _hourly_to_forecast(hour)) is not None
        ]

    async def async_get_forecasts_extra(self, type: str) -> ServiceResponse:
        """Return the forecast values that weather.get_forecasts has no field for."""
        if type == "hourly":
            return {
                "forecast": [
                    extra
                    for hour in self.coordinator.data.hourly
                    if (extra := self._hourly_extra(hour)) is not None
                ]
            }
        return {
            "forecast": [
                extra
                for day in self.coordinator.data.daily
                if (extra := self._daily_extra(day)) is not None
            ]
        }

    def _hourly_extra(self, hour: HourlyForecast) -> dict[str, JsonValueType] | None:
        """Return an hour's values that a Home Assistant forecast cannot hold."""
        if (timestamp := dt_util.parse_datetime(hour.time or "")) is None:
            return None
        return {
            "datetime": timestamp.isoformat(),
            "precipitation_type": hour.precip_type,
            "snow_accumulation": self._snow(hour.snow_accum),
            "snow_depth": self._snow(hour.snow_depth),
            "solar_radiation": hour.solar_radiation,
            "thunderstorm_probability": hour.thunder_prob,
            "visibility": self._visibility(hour.visibility),
        }

    def _daily_extra(self, day: DailyForecast) -> dict[str, JsonValueType] | None:
        """Return a day's values that a Home Assistant forecast cannot hold."""
        if (date := dt_util.parse_date(day.date or "")) is None:
            return None
        return {
            "datetime": dt_util.start_of_local_day(date).isoformat(),
            "apparent_templow": self._temperature(day.min_feels_like_temp),
            "max_humidity": day.max_rel_humidity,
            "min_humidity": day.min_rel_humidity,
            "min_dew_point": self._temperature(day.min_dew_point),
            "min_visibility": self._visibility(day.min_visibility),
            "snow_accumulation": self._snow(day.snow_accum),
            "snow_depth": self._snow(day.snow_depth),
            "sunshine_duration": day.sunhours,
            "solar_radiation_sum": day.solar_radiation_sum,
            "sunrise": _from_epoch(day.sunrise_epoch),
            "sunset": _from_epoch(day.sunset_epoch),
            "confidence": _CONFIDENCE.get(day.confidence or ""),
        }

    def _temperature(self, value: float | None) -> float | None:
        """Convert a temperature in °C to the entity's temperature unit."""
        if value is None:
            return None
        return round(
            UNIT_CONVERSIONS[ATTR_WEATHER_TEMPERATURE_UNIT](
                value, UnitOfTemperature.CELSIUS, self._temperature_unit
            ),
            _ROUNDING_PRECISION,
        )

    def _visibility(self, value: float | None) -> float | None:
        """Convert a distance in metres to the entity's visibility unit."""
        if value is None:
            return None
        return round(
            UNIT_CONVERSIONS[ATTR_WEATHER_VISIBILITY_UNIT](
                value, UnitOfLength.METERS, self._visibility_unit
            ),
            _ROUNDING_PRECISION,
        )

    def _snow(self, value: float | None) -> float | None:
        """Convert a snow thickness in cm to the entity's precipitation unit."""
        if value is None:
            return None
        return round(
            UNIT_CONVERSIONS[ATTR_WEATHER_PRECIPITATION_UNIT](
                value, UnitOfPrecipitationDepth.CENTIMETERS, self._precipitation_unit
            ),
            _ROUNDING_PRECISION,
        )


def _from_epoch(epoch: int | None) -> str | None:
    """Return a Unix time as an ISO 8601 timestamp in UTC."""
    if epoch is None:
        return None
    return dt_util.utc_from_timestamp(epoch).isoformat()
