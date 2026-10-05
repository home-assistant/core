"""Support for Open-Meteo weather."""

from datetime import datetime, time
from typing import cast, override

from open_meteo import Forecast as OpenMeteoForecast

from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_IS_DAYTIME,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_DEW_POINT,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
    ATTR_FORECAST_NATIVE_PRESSURE,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_TEMP_LOW,
    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WMO_TO_HA_CONDITION_MAP
from .coordinator import OpenMeteoConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OpenMeteoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Open-Meteo weather entity based on a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([OpenMeteoWeatherEntity(entry=entry, coordinator=coordinator)])


class OpenMeteoWeatherEntity(
    SingleCoordinatorWeatherEntity[DataUpdateCoordinator[OpenMeteoForecast]]
):
    """Defines an Open-Meteo weather entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    # Open-Meteo has no request parameter to set the pressure unit; it always
    # returns pressure_msl in hPa, so the native unit is safe to hardcode here.
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_visibility_unit = UnitOfLength.METERS
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(
        self,
        *,
        entry: OpenMeteoConfigEntry,
        coordinator: DataUpdateCoordinator[OpenMeteoForecast],
    ) -> None:
        """Initialize Open-Meteo weather entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = entry.entry_id

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Open-Meteo",
            name=entry.title,
        )

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        if (
            not self.coordinator.data.current
            or not self.coordinator.data.current.weather_code
        ):
            return None
        return WMO_TO_HA_CONDITION_MAP.get(
            self.coordinator.data.current.weather_code
            + (0 if self.coordinator.data.current.is_day else 100)
        )

    @property
    @override
    def cloud_coverage(self) -> int | None:
        """Return the Cloud coverage in %."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.cloud_cover

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.apparent_temperature

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.temperature_2m

    @property
    @override
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.pressure_msl

    @property
    @override
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.dew_point_2m

    @property
    @override
    def humidity(self) -> int | None:
        """Return the humidity."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.relative_humidity_2m

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.wind_gusts_10m

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.wind_speed_10m

    @property
    @override
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.wind_direction_10m

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.visibility

    @property
    @override
    def uv_index(self) -> float | None:
        """Return the UV index."""
        if not self.coordinator.data.current:
            return None
        return self.coordinator.data.current.uv_index

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self.coordinator.data.daily is None:
            return None

        forecasts: list[Forecast] = []

        daily = self.coordinator.data.daily
        for index, date in enumerate(self.coordinator.data.daily.time):
            _datetime = datetime.combine(date=date, time=time(0), tzinfo=dt_util.UTC)
            forecast = Forecast(
                datetime=_datetime.isoformat(),
            )

            if daily.weather_code is not None:
                forecast[ATTR_FORECAST_CONDITION] = WMO_TO_HA_CONDITION_MAP.get(
                    daily.weather_code[index]
                )

            if daily.apparent_temperature_max is not None:
                forecast[ATTR_FORECAST_NATIVE_APPARENT_TEMP] = (
                    daily.apparent_temperature_max[index]
                )

            if daily.cloud_cover_mean is not None:
                forecast[ATTR_FORECAST_CLOUD_COVERAGE] = daily.cloud_cover_mean[index]

            if daily.dew_point_2m_mean is not None:
                forecast[ATTR_FORECAST_NATIVE_DEW_POINT] = daily.dew_point_2m_mean[
                    index
                ]

            if daily.precipitation_probability_mean is not None:
                forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = cast(
                    int, daily.precipitation_probability_mean[index]
                )

            if daily.precipitation_sum is not None:
                forecast[ATTR_FORECAST_NATIVE_PRECIPITATION] = daily.precipitation_sum[
                    index
                ]

            if daily.pressure_msl_mean is not None:
                forecast[ATTR_FORECAST_NATIVE_PRESSURE] = daily.pressure_msl_mean[index]

            if daily.relative_humidity_2m_mean is not None:
                forecast[ATTR_FORECAST_HUMIDITY] = daily.relative_humidity_2m_mean[
                    index
                ]

            if daily.temperature_2m_max is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = daily.temperature_2m_max[index]

            if daily.temperature_2m_min is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP_LOW] = daily.temperature_2m_min[
                    index
                ]

            if daily.uv_index_max is not None:
                forecast[ATTR_FORECAST_UV_INDEX] = daily.uv_index_max[index]

            if daily.wind_direction_10m_dominant is not None:
                forecast[ATTR_FORECAST_WIND_BEARING] = (
                    daily.wind_direction_10m_dominant[index]
                )

            if daily.wind_gusts_10m_max is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = (
                    daily.wind_gusts_10m_max[index]
                )

            if daily.wind_speed_10m_max is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = daily.wind_speed_10m_max[
                    index
                ]

            forecasts.append(forecast)

        return forecasts

    @callback
    @override
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        if self.coordinator.data.hourly is None:
            return None

        forecasts: list[Forecast] = []

        # Can have data in the past: https://github.com/open-meteo/open-meteo/issues/699
        today = dt_util.utcnow()

        hourly = self.coordinator.data.hourly
        for index, _datetime in enumerate(self.coordinator.data.hourly.time):
            if _datetime.tzinfo is None:
                _datetime = _datetime.replace(tzinfo=dt_util.UTC)
            if _datetime < today:
                continue

            forecast = Forecast(
                datetime=_datetime.isoformat(),
            )

            if hourly.weather_code is not None:
                forecast[ATTR_FORECAST_CONDITION] = WMO_TO_HA_CONDITION_MAP.get(
                    hourly.weather_code[index]
                )

            if hourly.apparent_temperature is not None:
                forecast[ATTR_FORECAST_NATIVE_APPARENT_TEMP] = (
                    hourly.apparent_temperature[index]
                )

            if hourly.cloud_cover is not None:
                forecast[ATTR_FORECAST_CLOUD_COVERAGE] = hourly.cloud_cover[index]

            if hourly.dew_point_2m is not None:
                forecast[ATTR_FORECAST_NATIVE_DEW_POINT] = hourly.dew_point_2m[index]

            if hourly.is_day is not None:
                forecast[ATTR_FORECAST_IS_DAYTIME] = hourly.is_day[index]

            if hourly.precipitation is not None:
                forecast[ATTR_FORECAST_NATIVE_PRECIPITATION] = hourly.precipitation[
                    index
                ]

            if hourly.precipitation_probability is not None:
                forecast[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = (
                    hourly.precipitation_probability[index]
                )

            if hourly.pressure_msl is not None:
                forecast[ATTR_FORECAST_NATIVE_PRESSURE] = hourly.pressure_msl[index]

            if hourly.relative_humidity_2m is not None:
                forecast[ATTR_FORECAST_HUMIDITY] = hourly.relative_humidity_2m[index]

            if hourly.temperature_2m is not None:
                forecast[ATTR_FORECAST_NATIVE_TEMP] = hourly.temperature_2m[index]

            if hourly.uv_index is not None:
                forecast[ATTR_FORECAST_UV_INDEX] = hourly.uv_index[index]

            if hourly.wind_direction_10m is not None:
                forecast[ATTR_FORECAST_WIND_BEARING] = hourly.wind_direction_10m[index]

            if hourly.wind_gusts_10m is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_GUST_SPEED] = hourly.wind_gusts_10m[
                    index
                ]

            if hourly.wind_speed_10m is not None:
                forecast[ATTR_FORECAST_NATIVE_WIND_SPEED] = hourly.wind_speed_10m[index]

            forecasts.append(forecast)

        return forecasts
