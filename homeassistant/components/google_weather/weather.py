"""Weather entity."""

from typing import Any, override

from google_weather_api import (
    GoogleWeatherApiError,
    HourlyForecastResponse,
    PrecipitationSegment,
    QuantitativePrecipitationForecast,
    WeatherCondition,
)

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
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
    ATTR_WEATHER_PRECIPITATION_UNIT,
    UNIT_CONVERSIONS,
    CoordinatorWeatherEntity,
    Forecast,
    WeatherEntityFeature,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
    GoogleWeatherHourlyForecastCoordinator,
)
from .entity import GoogleWeatherBaseEntity

PARALLEL_UPDATES = 0

# Maps https://developers.google.com/maps/documentation/weather/weather-condition-icons
# to https://contributors.home-assistant.io/core/entities/weather/#conditions
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
    WeatherCondition.Type.CLEAR_AFTER_FOG_IN_THE_MORNING: ATTR_CONDITION_SUNNY,
    WeatherCondition.Type.CLEAR_BUT_LATER_TURNING_CLOUDY: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLEAR_BUT_LATER_TURNING_TO_RAIN_AND_SNOW_MAIN_CONSTITUENT_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_BUT_LATER_TURNING_TO_SNOW_AND_RAIN_MAIN_CONSTITUENT_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_BUT_THUNDERSTORMS_LATER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLEAR_IN_THE_MORNING_BUT_CLOUDY_IN_THE_EVENING: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLEAR_IN_THE_MORNING_WITH_BRIEF_RAIN_IN_THE_EVENING: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_MORNING_WITH_BRIEF_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_RAIN_AND_SNOW_RAIN_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_SNOW_AND_RAIN_SNOW_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_WITH_BRIEF_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_CLOUDS_LATER: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_RAIN_ACCOMPANIED_BY_THUNDER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_RAIN_AND_SNOW_RAIN_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_SNOW_AND_RAIN_SNOW_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLEAR_WITH_PERIODIC_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_RAIN_AFTER_MIDNIGHT: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_RAIN_IN_THE_NIGHT: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLEAR_WITH_SNOW_ALONG_THE_MOUNTAINS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLEAR_WITH_THUNDERSTORMS_ALONG_THE_MOUNTAINS: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLEAR_WITH_THUNDERSTORMS_IN_THE_AFTERNOON: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLOUDY_BUT_CLEAR_LATER: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLOUDY_BUT_LATER_TURNING_TO_RAIN_AND_SNOW_MAIN_CONSTITUENT_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_BUT_LATER_TURNING_TO_SNOW_AND_RAIN_MAIN_CONSTITUENT_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_BUT_PERIODICALLY_CLEAR_LATER: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLOUDY_BUT_THUNDERSTORMS_LATER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLOUDY_MORNING_WITH_BRIEF_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_PERIODICALLY_CLEAR: ATTR_CONDITION_PARTLYCLOUDY,
    WeatherCondition.Type.CLOUDY_SNOWING_IN_THE_EVENING: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_SNOWING_IN_THE_NIGHT: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_RAIN_AND_SNOW_RAIN_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_SNOW_AND_RAIN_SNOW_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_BRIEF_THUNDERSTORM: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_FOG_ON_THE_OCEAN_AND_AT_THE_SEASHORE: ATTR_CONDITION_FOG,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_RAIN: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_RAIN_ACCOMPANIED_BY_THUNDER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_RAIN_AND_SNOW_RAIN_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_SNOW_ACCOMPANIED_BY_THUNDER: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_SNOW_AND_RAIN_SNOW_AS_MAIN_CONSTITUENT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_PERIODIC_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_RAIN_AFTER_MIDNIGHT: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_RAIN_FROM_ABOUT_NOON: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_RAIN_FROM_EVENING: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_RAIN_LATER: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.CLOUDY_WITH_SNOW_FROM_AROUND_NOON: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.CLOUDY_WITH_SNOW_LATER: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.FOG: ATTR_CONDITION_FOG,
    WeatherCondition.Type.RAINSNOW_MIX_LATER_BECOMING_CLEAR_RAIN_AS_MAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAINSNOW_MIX_RAIN_AS_MAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAINY_BUT_PERIODICALLY_CLEAR: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_ACCOMPANIED_BY_LIGHTNING: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCondition.Type.RAIN_ACCOMPANIED_BY_WINDSTORM: ATTR_CONDITION_POURING,
    WeatherCondition.Type.RAIN_CLEAR_AT_NIGHT: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_CLEAR_FROM_AROUND_EVENING: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_CLEAR_FROM_AROUND_NOON: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_LATER_BECOMING_CLEAR: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_LATER_BECOMING_CLOUDY: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_LATER_BECOMING_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_LATER_WITH_PERIODIC_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_SNOW_AT_NIGHT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_SNOW_IN_THE_EVENING: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_TEMPORARILY_BECOMING_SLEET: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_THAT_PERIODICALLY_STOPS: ATTR_CONDITION_RAINY,
    WeatherCondition.Type.RAIN_WITH_BRIEF_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.RAIN_WITH_PERIODIC_SNOW: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOWRAIN_MIX_LATER_BECOMING_CLEAR_SNOW_AS_MAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOWRAIN_MIX_LATER_BECOMING_CLOUDY_SNOW_AS_MAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOWRAIN_MIX_SNOW_AS_MAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_ACCOMPANIED_BY_LIGHTNING: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_BECOMING_SLEET: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_LATER_CLEAR: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_LATER_CLOUDY: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_LATER_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_PERIODICALLY_CLEAR: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_THAT_PERIODICALLY_STOPS: ATTR_CONDITION_SNOWY,
    WeatherCondition.Type.SNOW_TURNING_TO_RAIN_AROUND_NOON: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_TURNING_TO_RAIN_IN_THE_EVENING: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_TURNING_TO_RAIN_IN_THE_NIGHT: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_WITH_BRIEF_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_WITH_BRIEF_SLEET: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.SNOW_WITH_PERIODIC_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.VERY_HOT: ATTR_CONDITION_SUNNY,
    WeatherCondition.Type.SLEET: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCondition.Type.HEAVY_RAIN_TO_RAINSTORM: ATTR_CONDITION_POURING,
}


def _get_condition(
    api_condition: WeatherCondition.Type, is_daytime: bool
) -> str | None:
    """Map Google Weather condition to Home Assistant condition."""
    cond = _CONDITION_MAP[api_condition]
    if cond == ATTR_CONDITION_SUNNY and not is_daytime:
        return ATTR_CONDITION_CLEAR_NIGHT
    return cond


# Values exposed in the get_minute_forecast action response. The API's enum names
# stay out of the response so that a change on Google's side cannot break automations.
_PRECIPITATION_TYPE_MAP: dict[
    PrecipitationSegment.DominantPrecipitationType, str | None
] = {
    PrecipitationSegment.DominantPrecipitationType.DOMINANT_PRECIPITATION_TYPE_UNSPECIFIED: None,
    PrecipitationSegment.DominantPrecipitationType.NONE: "none",
    PrecipitationSegment.DominantPrecipitationType.RAIN: "rain",
    PrecipitationSegment.DominantPrecipitationType.SNOW: "snow",
    PrecipitationSegment.DominantPrecipitationType.HAIL: "hail",
}

_PRECIPITATION_INTENSITY_MAP: dict[
    PrecipitationSegment.PrecipitationIntensity, str | None
] = {
    PrecipitationSegment.PrecipitationIntensity.PRECIPITATION_INTENSITY_UNSPECIFIED: None,
    PrecipitationSegment.PrecipitationIntensity.NO_INTENSITY: "none",
    PrecipitationSegment.PrecipitationIntensity.LIGHT: "light",
    PrecipitationSegment.PrecipitationIntensity.MID_LIGHT: "mid_light",
    PrecipitationSegment.PrecipitationIntensity.MODERATE: "moderate",
    PrecipitationSegment.PrecipitationIntensity.MID_MODERATE: "mid_moderate",
    PrecipitationSegment.PrecipitationIntensity.HEAVY: "heavy",
    PrecipitationSegment.PrecipitationIntensity.MID_HEAVY: "mid_heavy",
}


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

    def __init__(
        self,
        entry: GoogleWeatherConfigEntry,
        subentry: ConfigSubentry,
    ) -> None:
        """Initialize the weather entity."""
        subentry_runtime_data = entry.runtime_data.subentries_runtime_data[
            subentry.subentry_id
        ]
        self._daily_coordinator = subentry_runtime_data.coordinator_daily_forecast
        super().__init__(
            observation_coordinator=subentry_runtime_data.coordinator_observation,
            daily_coordinator=self._daily_coordinator,
            hourly_coordinator=subentry_runtime_data.coordinator_hourly_forecast,
            twice_daily_coordinator=self._daily_coordinator,
        )
        GoogleWeatherBaseEntity.__init__(self, entry, subentry)
        self._update_supported_features()
        self._api = entry.runtime_data.api
        self._latitude: float = subentry.data[CONF_LATITUDE]
        self._longitude: float = subentry.data[CONF_LONGITUDE]

    @callback
    def _update_supported_features(self) -> bool:
        """Update supported features from the daily forecast response."""
        features = (
            WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
        )
        if any(
            day.daytime_forecast is not None or day.nighttime_forecast is not None
            for day in self._daily_coordinator.data.forecast_days
        ):
            features |= WeatherEntityFeature.FORECAST_TWICE_DAILY
        if self._attr_supported_features == features:
            return False
        self._attr_supported_features = features
        return True

    @callback
    def _refresh_supported_features(self) -> None:
        """Refresh supported features and write state if they changed."""
        if self._update_supported_features():
            self.async_write_ha_state()

    async def async_get_minute_forecast(self) -> dict[str, Any]:
        """Return the precipitation nowcast for up to the next 6 hours."""
        try:
            response = await self._api.async_get_minute_forecast(
                latitude=self._latitude, longitude=self._longitude
            )
        except GoogleWeatherApiError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="minute_forecast_error",
                translation_placeholders={"error": str(err)},
            ) from err
        return {
            "start_time": response.overall_prediction_timeframe.start_time,
            "end_time": response.overall_prediction_timeframe.end_time,
            "segments": [
                {
                    "start_time": segment.time_frame.start_time,
                    "end_time": segment.time_frame.end_time,
                    "precipitation_type": _PRECIPITATION_TYPE_MAP[segment.type],
                    "precipitation_probability": segment.probability,
                    "precipitation": self._convert_precipitation(segment.qpf),
                    "snowfall_amount": self._convert_precipitation(
                        segment.snowfall_amount
                    ),
                    "intensity": _PRECIPITATION_INTENSITY_MAP[segment.intensity],
                }
                for segment in response.segments
            ],
        }

    def _convert_precipitation(
        self, amount: QuantitativePrecipitationForecast | None
    ) -> float | None:
        """Convert a precipitation amount to the entity's precipitation unit.

        The API always reports amounts in millimeters because the client is
        configured for metric units; expose them the same way weather.get_forecasts
        does, in the unit the weather entity uses. The value is not rounded:
        minute-level segments carry very small amounts that would collapse to
        zero in coarser units and no longer add up over the forecast.
        """
        if amount is None or amount.quantity is None:
            return None
        return UNIT_CONVERSIONS[ATTR_WEATHER_PRECIPITATION_UNIT](
            amount.quantity,
            UnitOfPrecipitationDepth.MILLIMETERS,
            self._precipitation_unit,
        )

    @property
    @override
    def condition(self) -> str | None:
        """Return the current condition."""
        return _get_condition(
            self.coordinator.data.weather_condition.type,
            self.coordinator.data.is_daytime,
        )

    @property
    @override
    def native_temperature(self) -> float | None:
        """Return the temperature."""
        return self.coordinator.data.temperature.degrees

    @property
    @override
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature."""
        return self.coordinator.data.feels_like_temperature.degrees

    @property
    @override
    def native_dew_point(self) -> float | None:
        """Return the dew point."""
        return self.coordinator.data.dew_point.degrees

    @property
    @override
    def humidity(self) -> int:
        """Return the humidity."""
        return self.coordinator.data.relative_humidity

    @property
    @override
    def uv_index(self) -> float:
        """Return the UV index."""
        return float(self.coordinator.data.uv_index)

    @property
    @override
    def native_pressure(self) -> float:
        """Return the pressure."""
        return self.coordinator.data.air_pressure.mean_sea_level_millibars

    @property
    @override
    def native_wind_gust_speed(self) -> float | None:
        """Return the wind gust speed."""
        gust = self.coordinator.data.wind.gust
        return gust.value if gust else None

    @property
    @override
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        return self.coordinator.data.wind.speed.value

    @property
    @override
    def wind_bearing(self) -> int:
        """Return the wind bearing."""
        return self.coordinator.data.wind.direction.degrees

    @property
    @override
    def native_visibility(self) -> float | None:
        """Return the visibility."""
        return self.coordinator.data.visibility.distance

    @property
    @override
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        cloud_cover = self.coordinator.data.cloud_cover
        return float(cloud_cover) if cloud_cover is not None else None

    @callback
    @override
    def _async_forecast_daily(self) -> list[Forecast] | None:
        """Return the daily forecast in native units."""
        self._refresh_supported_features()
        daily_data = self._daily_coordinator.data
        forecasts: list[Forecast] = []
        for item in daily_data.forecast_days:
            parts = [
                part
                for part in (
                    item.daytime_forecast,
                    item.nighttime_forecast,
                    item.full_day_forecast,
                )
                if part is not None
            ]
            if not parts:
                continue
            primary = parts[0]
            quantities = [
                part.precipitation.qpf.quantity
                for part in parts
                if part.precipitation.qpf.quantity is not None
            ]
            gusts = [
                part.wind.gust.value
                for part in parts
                if part.wind.gust and part.wind.gust.value is not None
            ]
            speeds = [
                part.wind.speed.value
                for part in parts
                if part.wind.speed.value is not None
            ]
            forecasts.append(
                {
                    ATTR_FORECAST_CONDITION: _get_condition(
                        primary.weather_condition.type, is_daytime=True
                    ),
                    ATTR_FORECAST_TIME: item.interval.start_time,
                    ATTR_FORECAST_HUMIDITY: primary.relative_humidity,
                    ATTR_FORECAST_PRECIPITATION_PROBABILITY: max(
                        part.precipitation.probability.percent for part in parts
                    ),
                    ATTR_FORECAST_CLOUD_COVERAGE: primary.cloud_cover,
                    ATTR_FORECAST_NATIVE_PRECIPITATION: (
                        sum(quantities) if len(quantities) == len(parts) else None
                    ),
                    ATTR_FORECAST_NATIVE_TEMP: item.max_temperature.degrees,
                    ATTR_FORECAST_NATIVE_TEMP_LOW: item.min_temperature.degrees,
                    ATTR_FORECAST_NATIVE_APPARENT_TEMP: (
                        item.feels_like_max_temperature.degrees
                    ),
                    ATTR_FORECAST_WIND_BEARING: primary.wind.direction.degrees,
                    ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: (
                        max(gusts) if gusts else None
                    ),
                    ATTR_FORECAST_NATIVE_WIND_SPEED: max(speeds) if speeds else None,
                    ATTR_FORECAST_UV_INDEX: primary.uv_index,
                }
            )
        return forecasts

    @callback
    @override
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
                ATTR_FORECAST_PRECIPITATION_PROBABILITY: (
                    item.precipitation.probability.percent
                ),
                ATTR_FORECAST_CLOUD_COVERAGE: item.cloud_cover,
                ATTR_FORECAST_NATIVE_PRECIPITATION: item.precipitation.qpf.quantity,
                ATTR_FORECAST_NATIVE_PRESSURE: (
                    item.air_pressure.mean_sea_level_millibars
                ),
                ATTR_FORECAST_NATIVE_TEMP: item.temperature.degrees,
                ATTR_FORECAST_NATIVE_APPARENT_TEMP: item.feels_like_temperature.degrees,
                ATTR_FORECAST_WIND_BEARING: item.wind.direction.degrees,
                ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: (
                    item.wind.gust.value if item.wind.gust else None
                ),
                ATTR_FORECAST_NATIVE_WIND_SPEED: item.wind.speed.value,
                ATTR_FORECAST_NATIVE_DEW_POINT: item.dew_point.degrees,
                ATTR_FORECAST_UV_INDEX: item.uv_index,
                ATTR_FORECAST_IS_DAYTIME: item.is_daytime,
            }
            for item in hourly_data.forecast_hours
        ]

    @callback
    @override
    def _async_forecast_twice_daily(self) -> list[Forecast] | None:
        """Return the twice daily forecast in native units."""
        self._refresh_supported_features()
        daily_data = self._daily_coordinator.data
        forecasts: list[Forecast] = []
        for item in daily_data.forecast_days:
            for is_daytime, part, temp, apparent_temp in (
                (
                    True,
                    item.daytime_forecast,
                    item.max_temperature.degrees,
                    item.feels_like_max_temperature.degrees,
                ),
                (
                    False,
                    item.nighttime_forecast,
                    item.min_temperature.degrees,
                    item.feels_like_min_temperature.degrees,
                ),
            ):
                if part is None:
                    continue
                forecasts.append(
                    {
                        ATTR_FORECAST_CONDITION: _get_condition(
                            part.weather_condition.type, is_daytime=is_daytime
                        ),
                        ATTR_FORECAST_TIME: part.interval.start_time,
                        ATTR_FORECAST_HUMIDITY: part.relative_humidity,
                        ATTR_FORECAST_PRECIPITATION_PROBABILITY: (
                            part.precipitation.probability.percent
                        ),
                        ATTR_FORECAST_CLOUD_COVERAGE: part.cloud_cover,
                        ATTR_FORECAST_NATIVE_PRECIPITATION: (
                            part.precipitation.qpf.quantity
                        ),
                        ATTR_FORECAST_NATIVE_TEMP: temp,
                        ATTR_FORECAST_NATIVE_APPARENT_TEMP: apparent_temp,
                        ATTR_FORECAST_WIND_BEARING: part.wind.direction.degrees,
                        ATTR_FORECAST_NATIVE_WIND_GUST_SPEED: (
                            part.wind.gust.value if part.wind.gust else None
                        ),
                        ATTR_FORECAST_NATIVE_WIND_SPEED: part.wind.speed.value,
                        ATTR_FORECAST_UV_INDEX: part.uv_index,
                        ATTR_FORECAST_IS_DAYTIME: is_daytime,
                    }
                )

        return forecasts
