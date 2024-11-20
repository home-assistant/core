"""Support for the AccuWeather service."""

from __future__ import annotations

from typing import cast

from homeassistant.components.weather import (
    ATTR_FORECAST_CLOUD_COVERAGE,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_HUMIDITY,
    ATTR_FORECAST_NATIVE_APPARENT_TEMP,
    ATTR_FORECAST_NATIVE_PRECIPITATION,
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.dt import utc_from_timestamp

from .const import (
    API_METRIC,
    ATTR_DIRECTION,
    ATTR_SPEED,
    ATTR_VALUE,
    ATTRIBUTION,
    CONDITION_MAP,
)
from .coordinator import (
    AccuWeatherConfigEntry,
    AccuWeatherDailyForecastDataUpdateCoordinator,
    AccuWeatherData,
    AccuWeatherObservationDataUpdateCoordinator,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AccuWeatherConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add a AccuWeather weather entity from a config_entry."""
    async_add_entities([AccuWeatherEntity(entry.runtime_data)])


class AccuWeatherEntity(
    CoordinatorWeatherEntity[
        AccuWeatherObservationDataUpdateCoordinator,
        AccuWeatherDailyForecastDataUpdateCoordinator,
    ]
):
    """Define an AccuWeather entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, accuweather_data: AccuWeatherData) -> None:
        """Initialize."""
        super().__init__(
            observation_coordinator=accuweather_data.coordinator_observation,
            daily_coordinator=accuweather_data.coordinator_daily_forecast,
        )

        self._attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_visibility_unit = UnitOfLength.KILOMETERS
        self._attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
        self._attr_unique_id = accuweather_data.coordinator_observation.location_key
        self._attr_attribution = ATTRIBUTION
        self._attr_device_info = accuweather_data.coordinator_observation.device_info
        self._attr_supported_features = WeatherEntityFeature.FORECAST_DAILY

        self.observation_coordinator = accuweather_data.coordinator_observation
        self.daily_coordinator = accuweather_data.coordinator_daily_forecast

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return CONDITION_MAP.get(self.observation_coordinator.data["WeatherIcon"])

    @property
    def cloud_coverage(self) -> float:
        """Return the Cloud coverage in %."""
        return cast(float, self.observation_coordinator.data["CloudCover"])

    @property
    def native_apparent_temperature(self) -> float:
        """Return the apparent temperature."""
        return cast(
            float,
            self.observation_coordinator.data["ApparentTemperature"][API_METRIC][
                ATTR_VALUE
            ],
        )

    @property
    def native_temperature(self) -> float:
        """Return the temperature."""
        return cast(
            float,
            self.observation_coordinator.data["Temperature"][API_METRIC][ATTR_VALUE],
        )

    @property
    def native_pressure(self) -> float:
        """Return the pressure."""
        return cast(
            float, self.observation_coordinator.data["Pressure"][API_METRIC][ATTR_VALUE]
        )

    @property
    def native_dew_point(self) -> float:
        """Return the dew point."""
        return cast(
            float, self.observation_coordinator.data["DewPoint"][API_METRIC][ATTR_VALUE]
        )

    @property
    def humidity(self) -> int:
        """Return the humidity."""
        return cast(int, self.observation_coordinator.data["RelativeHumidity"])

    @property
    def native_wind_gust_speed(self) -> float:
        """Return the wind gust speed."""
        return cast(
            float,
            self.observation_coordinator.data["WindGust"][ATTR_SPEED][API_METRIC][
                ATTR_VALUE
            ],
        )

    @property
    def native_wind_speed(self) -> float:
        """Return the wind speed."""
        return cast(
            float,
            self.observation_coordinator.data["Wind"][ATTR_SPEED][API_METRIC][
                ATTR_VALUE
            ],
        )

    @property
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return cast(
            int, self.observation_coordinator.data["Wind"][ATTR_DIRECTION]["Degrees"]
        )

    @property
    def native_visibility(self) -> float:
        """Return the visibility."""
        return cast(
            float,
            self.observation_coordinator.data["Visibility"][API_METRIC][ATTR_VALUE],
        )

    @property
    def uv_index(self) -> float:
        """Return the UV index."""
        return cast(float, self.observation_coordinator.data["UVIndex"])

    @callback
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        return [
            {
                ATTR_FORECAST_TIME: utc_from_timestamp(item["EpochDate"]).isoformat(),
                ATTR_FORECAST_CLOUD_COVERAGE: item["CloudCoverDay"],
                ATTR_FORECAST_HUMIDITY: item["RelativeHumidityDay"]["Average"],
                ATTR_FORECAST_NATIVE_TEMP: item["TemperatureMax"][ATTR_VALUE],
                ATTR_FORECAST_NATIVE_TEMP_LOW: item["TemperatureMin"][ATTR_VALUE],
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item["RealFeelTemperatureMax"][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_NATIVE_PRECIPITATION: item["TotalLiquidDay"][ATTR_VALUE],
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: item[
                    "PrecipitationProbabilityDay"
                ],
                ATTR_FORECAST_NATIVE_WIND_SPEED: item["WindDay"][ATTR_SPEED][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: item["WindGustDay"][ATTR_SPEED][
                    ATTR_VALUE
                ],
                ATTR_FORECAST_UV_INDEX: item["UVIndex"][ATTR_VALUE],
                ATTR_FORECAST_WIND_BEARING: item["WindDay"][ATTR_DIRECTION]["Degrees"],
                ATTR_FORECAST_CONDITION: CONDITION_MAP.get(item["IconDay"]),
            }
            for item in self.daily_coordinator.data
        ]
