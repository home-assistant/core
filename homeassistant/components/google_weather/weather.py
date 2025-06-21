"""Weather entity."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
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
    GoogleWeatherRuntimeData,
)

PARALLEL_UPDATES = 0

_LOGGER = logging.getLogger(__name__)

# Maps https://developers.google.com/maps/documentation/weather/weather-condition-icons
# to https://developers.home-assistant.io/docs/core/entity/weather/#recommended-values-for-state-and-condition
_CONDITION_MAP = {
    "CLEAR": ATTR_CONDITION_SUNNY,  # or ATTR_CONDITION_CLEAR_NIGHT if night
    "MOSTLY_CLEAR": ATTR_CONDITION_PARTLYCLOUDY,
    "PARTLY_CLOUDY": ATTR_CONDITION_PARTLYCLOUDY,
    "MOSTLY_CLOUDY": ATTR_CONDITION_CLOUDY,
    "CLOUDY": ATTR_CONDITION_CLOUDY,
    "WINDY": ATTR_CONDITION_WINDY,
    "WIND_AND_RAIN": ATTR_CONDITION_RAINY,
    "LIGHT_RAIN_SHOWERS": ATTR_CONDITION_RAINY,
    "CHANCE_OF_SHOWERS": ATTR_CONDITION_RAINY,
    "SCATTERED_SHOWERS": ATTR_CONDITION_RAINY,
    "RAIN_SHOWERS": ATTR_CONDITION_RAINY,
    "HEAVY_RAIN_SHOWERS": ATTR_CONDITION_POURING,
    "LIGHT_TO_MODERATE_RAIN": ATTR_CONDITION_RAINY,
    "MODERATE_TO_HEAVY_RAIN": ATTR_CONDITION_POURING,
    "RAIN": ATTR_CONDITION_RAINY,
    "LIGHT_RAIN": ATTR_CONDITION_RAINY,
    "HEAVY_RAIN": ATTR_CONDITION_POURING,
    "RAIN_PERIODICALLY_HEAVY": ATTR_CONDITION_POURING,
    "LIGHT_SNOW_SHOWERS": ATTR_CONDITION_SNOWY,
    "CHANCE_OF_SNOW_SHOWERS": ATTR_CONDITION_SNOWY,
    "SCATTERED_SNOW_SHOWERS": ATTR_CONDITION_SNOWY,
    "SNOW_SHOWERS": ATTR_CONDITION_SNOWY,
    "HEAVY_SNOW_SHOWERS": ATTR_CONDITION_SNOWY,
    "LIGHT_TO_MODERATE_SNOW": ATTR_CONDITION_SNOWY,
    "MODERATE_TO_HEAVY_SNOW": ATTR_CONDITION_SNOWY,
    "SNOW": ATTR_CONDITION_SNOWY,
    "LIGHT_SNOW": ATTR_CONDITION_SNOWY,
    "HEAVY_SNOW": ATTR_CONDITION_SNOWY,
    "SNOWSTORM": ATTR_CONDITION_SNOWY,
    "SNOW_PERIODICALLY_HEAVY": ATTR_CONDITION_SNOWY,
    "HEAVY_SNOW_STORM": ATTR_CONDITION_SNOWY,
    "BLOWING_SNOW": ATTR_CONDITION_SNOWY,
    "RAIN_AND_SNOW": ATTR_CONDITION_SNOWY_RAINY,
    "HAIL": ATTR_CONDITION_HAIL,
    "HAIL_SHOWERS": ATTR_CONDITION_HAIL,
    "THUNDERSTORM": ATTR_CONDITION_LIGHTNING_RAINY,
    "THUNDERSHOWER": ATTR_CONDITION_LIGHTNING_RAINY,
    "LIGHT_THUNDERSTORM_RAIN": ATTR_CONDITION_LIGHTNING_RAINY,
    "SCATTERED_THUNDERSTORMS": ATTR_CONDITION_LIGHTNING,
    "HEAVY_THUNDERSTORM": ATTR_CONDITION_LIGHTNING_RAINY,
}


def _get_condition(data: dict[str, Any], is_daytime: bool | None = None) -> str | None:
    api_cond = data["weatherCondition"]["type"]
    cond = _CONDITION_MAP.get(api_cond)
    if cond is None:
        _LOGGER.warning("Unknown condition from Google Weather API: %s", api_cond)
    if cond == ATTR_CONDITION_SUNNY:
        if is_daytime is None:
            is_daytime = bool(data["isDaytime"])
        if not is_daytime:
            cond = ATTR_CONDITION_CLEAR_NIGHT
    return cond


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    async_add_entities([GoogleWeatherEntity(entry.runtime_data)])


class GoogleWeatherEntity(
    CoordinatorWeatherEntity[
        GoogleWeatherCurrentConditionsCoordinator,
        GoogleWeatherDailyForecastCoordinator,
        GoogleWeatherHourlyForecastCoordinator,
        GoogleWeatherDailyForecastCoordinator,
    ]
):
    """Representation of a Google Weather entity."""

    _attr_attribution = "Data from Google Weather"

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.MBAR
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    _attr_has_entity_name = True
    _attr_name = None

    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY
        | WeatherEntityFeature.FORECAST_HOURLY
        | WeatherEntityFeature.FORECAST_TWICE_DAILY
    )

    def __init__(
        self,
        runtime_data: GoogleWeatherRuntimeData,
    ) -> None:
        """Initialize the weather entity."""
        super().__init__(
            observation_coordinator=runtime_data.coordinator_observation,
            daily_coordinator=runtime_data.coordinator_daily_forecast,
            hourly_coordinator=runtime_data.coordinator_hourly_forecast,
            twice_daily_coordinator=runtime_data.coordinator_daily_forecast,
        )
        self._attr_unique_id = (
            runtime_data.coordinator_observation.config_entry.unique_id
        )
        self._attr_device_info = runtime_data.coordinator_observation.device_info

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return _get_condition(self.coordinator.data)

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return float(self.coordinator.data["temperature"]["degrees"])

    @property
    def native_apparent_temperature(self) -> float:
        """Return the apparent temperature."""
        return float(self.coordinator.data["feelsLikeTemperature"]["degrees"])

    @property
    def native_dew_point(self) -> float:
        """Return the dew point."""
        return float(self.coordinator.data["dewPoint"]["degrees"])

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return int(self.coordinator.data["relativeHumidity"])

    @property
    def uv_index(self) -> float:
        """Return the UV index."""
        return float(self.coordinator.data["uvIndex"])

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return float(self.coordinator.data["airPressure"]["meanSeaLevelMillibars"])

    @property
    def native_wind_gust_speed(self) -> float:
        """Return the wind gust speed."""
        return float(self.coordinator.data["wind"]["gust"]["value"])

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return float(self.coordinator.data["wind"]["speed"]["value"])

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return int(self.coordinator.data["wind"]["direction"]["degrees"])

    @property
    def native_visibility(self) -> float:
        """Return the visibility."""
        return float(self.coordinator.data["visibility"]["distance"])

    @property
    def cloud_coverage(self) -> float:
        """Return the Cloud coverage in %."""
        return float(self.coordinator.data["cloudCover"])

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        coordinator = self.forecast_coordinators["daily"]
        assert coordinator
        daily_data = coordinator.data
        return [
            {
                ATTR_FORECAST_CONDITION: _get_condition(
                    item["daytimeForecast"], is_daytime=True
                ),
                ATTR_FORECAST_TIME: item["interval"]["startTime"],
                ATTR_FORECAST_HUMIDITY: item["daytimeForecast"]["relativeHumidity"],
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: max(
                    item["daytimeForecast"]["precipitation"]["probability"]["percent"],
                    item["nighttimeForecast"]["precipitation"]["probability"][
                        "percent"
                    ],
                ),
                ATTR_FORECAST_CLOUD_COVERAGE: item["daytimeForecast"]["cloudCover"],
                ATTR_FORECAST_NATIVE_PRECIPITATION: (
                    item["daytimeForecast"]["precipitation"]["qpf"]["quantity"]
                    + item["nighttimeForecast"]["precipitation"]["qpf"]["quantity"]
                ),
                ATTR_FORECAST_NATIVE_TEMP: item["maxTemperature"]["degrees"],
                ATTR_FORECAST_NATIVE_TEMP_LOW: item["minTemperature"]["degrees"],
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item["feelsLikeMaxTemperature"][
                    "degrees"
                ],
                ATTR_FORECAST_WIND_BEARING: item["daytimeForecast"]["wind"][
                    "direction"
                ]["degrees"],
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: max(
                    item["daytimeForecast"]["wind"]["gust"]["value"],
                    item["nighttimeForecast"]["wind"]["gust"]["value"],
                ),
                ATTR_FORECAST_NATIVE_WIND_SPEED: max(
                    item["daytimeForecast"]["wind"]["speed"]["value"],
                    item["nighttimeForecast"]["wind"]["speed"]["value"],
                ),
                ATTR_FORECAST_UV_INDEX: item["daytimeForecast"]["uvIndex"],
            }
            for item in daily_data["forecastDays"]
        ]

    @callback
    def _async_forecast_hourly(self) -> list[Forecast] | None:
        """Return the hourly forecast in native units."""
        coordinator = self.forecast_coordinators["hourly"]
        assert coordinator
        hourly_data = coordinator.data
        return [
            {
                ATTR_FORECAST_CONDITION: _get_condition(item),
                ATTR_FORECAST_TIME: item["interval"]["startTime"],
                ATTR_FORECAST_HUMIDITY: item["relativeHumidity"],
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: item["precipitation"][
                    "probability"
                ]["percent"],
                ATTR_FORECAST_CLOUD_COVERAGE: item["cloudCover"],
                ATTR_FORECAST_NATIVE_PRECIPITATION: item["precipitation"]["qpf"][
                    "quantity"
                ],
                ATTR_FORECAST_NATIVE_PRESSURE: item["airPressure"][
                    "meanSeaLevelMillibars"
                ],
                ATTR_FORECAST_NATIVE_TEMP: item["temperature"]["degrees"],
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item["feelsLikeTemperature"][
                    "degrees"
                ],
                ATTR_FORECAST_WIND_BEARING: item["wind"]["direction"]["degrees"],
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: item["wind"]["gust"]["value"],
                ATTR_FORECAST_NATIVE_WIND_SPEED: item["wind"]["speed"]["value"],
                ATTR_FORECAST_NATIVE_DEW_POINT: item["dewPoint"]["degrees"],
                ATTR_FORECAST_UV_INDEX: item["uvIndex"],
                ATTR_FORECAST_IS_DAYTIME: item["isDaytime"],
            }
            for item in hourly_data["forecastHours"]
        ]

    @callback
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        coordinator = self.forecast_coordinators["twice_daily"]
        assert coordinator
        daily_data = coordinator.data
        forecasts: list[Forecast] = []
        for item in daily_data["forecastDays"]:
            # Process daytime forecast
            if day_forecast := item.get("daytimeForecast"):
                forecasts.append(
                    {
                        ATTR_FORECAST_CONDITION: _get_condition(
                            day_forecast, is_daytime=True
                        ),
                        ATTR_FORECAST_TIME: day_forecast["interval"]["startTime"],
                        ATTR_FORECAST_HUMIDITY: day_forecast["relativeHumidity"],
                        ATTR_FORECAST_PRECIPITATION_PROBABILITY: day_forecast[
                            "precipitation"
                        ]["probability"]["percent"],
                        ATTR_FORECAST_CLOUD_COVERAGE: day_forecast["cloudCover"],
                        ATTR_FORECAST_NATIVE_PRECIPITATION: day_forecast[
                            "precipitation"
                        ]["qpf"]["quantity"],
                        ATTR_FORECAST_NATIVE_TEMP: item["maxTemperature"]["degrees"],
                        ATTR_FORECAST_NATIVE_APPARENT_TEMP: item[
                            "feelsLikeMaxTemperature"
                        ]["degrees"],
                        ATTR_FORECAST_WIND_BEARING: day_forecast["wind"]["direction"][
                            "degrees"
                        ],
                        ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: day_forecast["wind"][
                            "gust"
                        ]["value"],
                        ATTR_FORECAST_NATIVE_WIND_SPEED: day_forecast["wind"]["speed"][
                            "value"
                        ],
                        ATTR_FORECAST_UV_INDEX: day_forecast["uvIndex"],
                        ATTR_FORECAST_IS_DAYTIME: True,
                    }
                )

            # Process nighttime forecast
            if night_forecast := item.get("nighttimeForecast"):
                forecasts.append(
                    {
                        ATTR_FORECAST_CONDITION: _get_condition(
                            night_forecast, is_daytime=False
                        ),
                        ATTR_FORECAST_TIME: night_forecast["interval"]["startTime"],
                        ATTR_FORECAST_HUMIDITY: night_forecast["relativeHumidity"],
                        ATTR_FORECAST_PRECIPITATION_PROBABILITY: night_forecast[
                            "precipitation"
                        ]["probability"]["percent"],
                        ATTR_FORECAST_CLOUD_COVERAGE: night_forecast["cloudCover"],
                        ATTR_FORECAST_NATIVE_PRECIPITATION: night_forecast[
                            "precipitation"
                        ]["qpf"]["quantity"],
                        ATTR_FORECAST_NATIVE_TEMP: item["minTemperature"]["degrees"],
                        ATTR_FORECAST_NATIVE_APPARENT_TEMP: item[
                            "feelsLikeMinTemperature"
                        ]["degrees"],
                        ATTR_FORECAST_WIND_BEARING: night_forecast["wind"]["direction"][
                            "degrees"
                        ],
                        ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: night_forecast["wind"][
                            "gust"
                        ]["value"],
                        ATTR_FORECAST_NATIVE_WIND_SPEED: night_forecast["wind"][
                            "speed"
                        ]["value"],
                        ATTR_FORECAST_UV_INDEX: night_forecast["uvIndex"],
                        ATTR_FORECAST_IS_DAYTIME: False,
                    }
                )

        return forecasts
