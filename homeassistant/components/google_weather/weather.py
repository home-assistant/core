"""Weather entity."""

from __future__ import annotations

from google_weather_api import (
    DailyForecastResponse,
    HourlyForecastResponse,
    WeatherCondition,
)

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
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
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_UV_INDEX,
    ATTR_FORECAST_WIND_BEARING,
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
    GoogleWeatherHourlyForecastCoordinator,
)
from .entity import GoogleWeatherBaseEntity

PARALLEL_UPDATES = 0

# Maps https://developers.google.com/maps/documentation/weather/weather-condition-icons
# to https://developers.home-assistant.io/docs/core/entity/weather/#recommended-values-for-state-and-condition
_CONDITION_MAP: dict[WeatherCondition.Type, str | None] = {
    WeatherCondition.Type.TYPE_UNSPECIFIED: None,
    WeatherCondition.Type.CLEAR: ATTR_CONDITION_SUNNY,
    WeatherCondition.Type.MOSTLY_CLEAR: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.PARTLY_CLOUDY: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.MOSTLY_CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCondition.Type.CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCondition.Type.WINDY: ATTR_CONDITION_WINDY,
    WeatherCondition.Type.WIND_AND_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.LIGHT_RAIN_SHOWERS: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CHANCE_OF_SHOWERS: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.SCATTERED_SHOWERS: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_SHOWERS: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.HEAVY_RAIN_SHOWERS: ATTR_CONDITION_POURING,
    WeatherCondition.Type.LIGHT_TO_MODERATE_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.MODERATE_TO_HEAVY_RAIN: ATTR_CONDITION_POURING,
    WeatherCondition.Type.RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.LIGHT_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.HEAVY_RAIN: ATTR_CONDITION_POURING,
    WeatherCondition.Type.RAIN_PERIODICALLY_HEAVY: ATTR_CONDITION_POURING,
    WeatherCondition.Type.LIGHT_SNOW_SHOWERS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CHANCE_OF_SNOW_SHOWERS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SCATTERED_SNOW_SHOWERS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_SHOWERS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.HEAVY_SNOW_SHOWERS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.LIGHT_TO_MODERATE_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.MODERATE_TO_HEAVY_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.LIGHT_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.HEAVY_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOWSTORM: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_PERIODICALLY_HEAVY: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.HEAVY_SNOW_STORM: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.BLOWING_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.RAIN_AND_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.HAIL: ATTR_CONDITION_HAIL,
    WeatherCondition.Type.HAIL_SHOWERS: ATTR_CONDITION_HAIL,
    WeatherCondition.Type.THUNDERSTORM: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.THUNDERSHOWER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.LIGHT_THUNDERSTORM_RAIN: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.SCATTERED_THUNDERSTORMS: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.HEAVY_THUNDERSTORM: ATTR_CONDITION_LIGHTNING_RAINY,
}


def _get_condition(
    api_condition: WeatherCondition.Type, is_daytime: bool
) -> str | None:
    """Map Google Weather condition to Home Assistant condition."""
    cond = _CONDITION_MAP[api_condition]
    if cond == ATTR_CONDITION_SUNNY and not is_daytime:
        return ATTR_CONDITION_CLEAR_NIGHT
    return cond


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    for subentry in entry.subentries.values():
        async_add_entities(
            [GoogleWeatherEntity(entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class GoogleWeatherEntity(
    CoordinatorWeatherEntity[
        GoogleWeatherCurrentConditionsCoordinator,
        GoogleWeatherDailyForecastCoordinator,
        GoogleWeatherHourlyForecastCoordinator,
        GoogleWeatherDailyForecastCoordinator,
    ],
    GoogleWeatherBaseEntity,
):
    """Representation of a Google Weather entity."""

    _attr_attribution = "Data from Google Weather"

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.MBAR
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    _attr_name = None

    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the weather entity."""
        subentry_runtime_data = entry.runtime_data.subentries_runtime_data[
            subentry.subentry_id
        ]
        super().__init__(
            observation_coordinator=subentry_runtime_data.coordinator_observation,
            daily_coordinator=subentry_runtime_data.coordinator_daily_forecast,
            hourly_coordinator=subentry_runtime_data.coordinator_hourly_forecast,
            twice_daily_coordinator=subentry_runtime_data.coordinator_daily_forecast,
        )
        GoogleWeatherBaseEntity.__init__(self, entry, subentry)

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return _get_condition(
            self.coordinator.data.weather_condition.type,
            self.coordinator.data.is_daytime,
        )

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return self.coordinator.data.temperature.degrees

    @property
    def native_apparent_temperature(self) -> float:
        """Return the apparent temperature."""
        return self.coordinator.data.feels_like_temperature.degrees

    @property
    def native_dew_point(self) -> float:
        """Return the dew point."""
        return self.coordinator.data.dew_point.degrees

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return self.coordinator.data.relative_humidity

    @property
    def uv_index(self) -> float:
        """Return the UV index."""
        return float(self.coordinator.data.uv_index)

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return self.coordinator.data.air_pressure.mean_sea_level_millibars

    @property
    def native_wind_gust_speed(self) -> float:
        """Return the wind gust speed."""
        return self.coordinator.data.wind.gust.value

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return self.coordinator.data.wind.speed.value

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return self.coordinator.data.wind.direction.degrees

    @property
    def native_visibility(self) -> float:
        """Return the visibility."""
        return self.coordinator.data.visibility.distance

    @property
    def cloud_coverage(self) -> float:
        """Return the Cloud coverage in %."""
        return float(self.coordinator.data.cloud_cover)

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        coordinator = self.forecast_coordinators["daily"]
        assert coordinator
        daily_data = coordinator.data
        assert isinstance(daily_data, DailyForecastResponse)
        return [
            {
                ATTR_FORECAST_CONDITION: _get_condition(
                    item.daytime_forecast.weather_condition.type, is_daytime=True
                ),
                ATTR_FORECAST_TIME: item.interval.start_time,
                ATTR_FORECAST_HUMIDITY: item.daytime_forecast.relative_humidity,
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: max(
                    item.daytime_forecast.precipitation.probability.percent,
                    item.nighttime_forecast.precipitation.probability.percent,
                ),
                ATTR_FORECAST_CLOUD_COVERAGE: item.daytime_forecast.cloud_cover,
                ATTR_FORECAST_NATIVE_PRECIPITATION: (
                    item.daytime_forecast.precipitation.qpf.quantity
                    + item.nighttime_forecast.precipitation.qpf.quantity
                ),
                ATTR_FORECAST_NATIVE_TEMP: item.max_temperature.degrees,
                ATTR_FORECAST_NATIVE_TEMP_LOW: item.min_temperature.degrees,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: (
                    item.feels_like_max_temperature.degrees
                ),
                ATTR_FORECAST_WIND_BEARING: item.daytime_forecast.wind.direction.degrees,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: max(
                    item.daytime_forecast.wind.gust.value,
                    item.nighttime_forecast.wind.gust.value,
                ),
                ATTR_FORECAST_NATIVE_WIND_SPEED: max(
                    item.daytime_forecast.wind.speed.value,
                    item.nighttime_forecast.wind.speed.value,
                ),
                ATTR_FORECAST_UV_INDEX: item.daytime_forecast.uv_index,
            }
            for item in daily_data.forecast_days
        ]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        coordinator = self.forecast_coordinators["hourly"]
        assert coordinator
        hourly_data = coordinator.data
        assert isinstance(hourly_data, HourlyForecastResponse)
        return [
            {
                ATTR_FORECAST_CONDITION: _get_condition(
                    item.weather_condition.type, item.is_daytime
                ),
                ATTR_FORECAST_TIME: item.interval.start_time,
                ATTR_FORECAST_HUMIDITY: item.relative_humidity,
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: item.precipitation.probability.percent,
                ATTR_FORECAST_CLOUD_COVERAGE: item.cloud_cover,
                ATTR_FORECAST_NATIVE_PRECIPITATION: item.precipitation.qpf.quantity,
                ATTR_FORECAST_NATIVE_PRESSURE: item.air_pressure.mean_sea_level_millibars,
                ATTR_FORECAST_NATIVE_TEMP: item.temperature.degrees,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item.feels_like_temperature.degrees,
                ATTR_FORECAST_WIND_BEARING: item.wind.direction.degrees,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: item.wind.gust.value,
                ATTR_FORECAST_NATIVE_WIND_SPEED: item.wind.speed.value,
                ATTR_FORECAST_NATIVE_DEW_POINT: item.dew_point.degrees,
                ATTR_FORECAST_UV_INDEX: item.uv_index,
                ATTR_FORECAST_IS_DAYTIME: item.is_daytime,
            }
            for item in hourly_data.forecast_hours
        ]

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        coordinator = self.forecast_coordinators["twice_daily"]
        assert coordinator
        daily_data = coordinator.data
        assert isinstance(daily_data, DailyForecastResponse)
        forecasts: list[Forecast] = []
        for item in daily_data.forecast_days:
            # Process daytime forecast
            day_forecast = item.daytime_forecast
            forecasts.append(
                {
                    ATTR_FORECAST_CONDITION: _get_condition(
                        day_forecast.weather_condition.type, is_daytime=True
                    ),
                    ATTR_FORECAST_TIME: day_forecast.interval.start_time,
                    ATTR_FORECAST_HUMIDITY: day_forecast.relative_humidity,
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: day_forecast.precipitation.probability.percent,
                    ATTR_FORECAST_CLOUD_COVERAGE: day_forecast.cloud_cover,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: day_forecast.precipitation.qpf.quantity,
                    ATTR_FORECAST_NATIVE_TEMP: item.max_temperature.degrees,
                    ATTR_FORECAST_NATIVE_APPARENT_TEMP: item.feels_like_max_temperature.degrees,
                    ATTR_FORECAST_WIND_BEARING: day_forecast.wind.direction.degrees,
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: day_forecast.wind.gust.value,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: day_forecast.wind.speed.value,
                    ATTR_FORECAST_UV_INDEX: day_forecast.uv_index,
                    ATTR_FORECAST_IS_DAYTIME: True,
                }
            )

            # Process nighttime forecast
            night_forecast = item.nighttime_forecast
            forecasts.append(
                {
                    ATTR_FORECAST_CONDITION: _get_condition(
                        night_forecast.weather_condition.type, is_daytime=False
                    ),
                    ATTR_FORECAST_TIME: night_forecast.interval.start_time,
                    ATTR_FORECAST_HUMIDITY: night_forecast.relative_humidity,
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: night_forecast.precipitation.probability.percent,
                    ATTR_FORECAST_CLOUD_COVERAGE: night_forecast.cloud_cover,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: night_forecast.precipitation.qpf.quantity,
                    ATTR_FORECAST_NATIVE_TEMP: item.min_temperature.degrees,
                    ATTR_FORECAST_NATIVE_APPARENT_TEMP: item.feels_like_min_temperature.degrees,
                    ATTR_FORECAST_WIND_BEARING: night_forecast.wind.direction.degrees,
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: night_forecast.wind.gust.value,
                    ATTR_FORECAST_NATIVE_WIND_SPEED: night_forecast.wind.speed.value,
                    ATTR_FORECAST_UV_INDEX: night_forecast.uv_index,
                    ATTR_FORECAST_IS_DAYTIME: False,
                }
            )

        return forecasts
