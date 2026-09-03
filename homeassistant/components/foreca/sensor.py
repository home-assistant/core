"""Sensor platform for the Foreca integration."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import override

from pyforeca import (
    AirQualityForecast,
    CurrentWeather,
    DailyForecast,
    HourlyForecast,
    Observation,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator, ForecaWeatherData
from .entity import ForecaEntity

PARALLEL_UPDATES = 0

AQ_FORECAST_DAYS = (1, 2, 3)


@dataclass(frozen=True, kw_only=True)
class ForecaSensorDescription(SensorEntityDescription):
    """Class describing Foreca sensor entities."""

    value_fn: Callable[[ForecaWeatherData], float | str | datetime | None]


def _nowcast(
    field_fn: Callable[[AirQualityForecast], float | str | None],
) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read a field from the current-hour air quality nowcast."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        if data.air_quality is None:
            return None
        return field_fn(data.air_quality)

    return value_fn


def _current(
    field_fn: Callable[[CurrentWeather], float | str | None],
) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read a field from the current conditions."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        return field_fn(data.current)

    return value_fn


def _this_hour(
    field_fn: Callable[[HourlyForecast], float | str | None],
) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read a field from the hourly forecast step covering now."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        if not data.hourly:
            return None
        return field_fn(data.hourly[0])

    return value_fn


def _today(
    field_fn: Callable[[DailyForecast], float | str | None],
) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read a field from today's daily forecast."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        if not data.daily:
            return None
        return field_fn(data.daily[0])

    return value_fn


def _observed(
    field_fn: Callable[[Observation], float | str | None],
) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read a field from the nearest station's latest observation."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        if data.observation is None:
            return None
        return field_fn(data.observation)

    return value_fn


def _nowcast_average(data: ForecaWeatherData) -> float | None:
    """Average precipitation rate over the nowcast hour."""
    rates = [s.precip_rate for s in data.minutely if s.precip_rate is not None]
    if not rates:
        return None
    return round(sum(rates) / len(rates), 2)


def _nowcast_total(data: ForecaWeatherData) -> float | None:
    """Precipitation accumulating over the nowcast hour, from per-minute rates."""
    rates = [s.precip_rate for s in data.minutely if s.precip_rate is not None]
    if not rates:
        return None
    return round(sum(rates) / 60, 2)


def _nowcast_start(data: ForecaWeatherData) -> datetime | None:
    """Timestamp of the first nowcast minute with precipitation, if any."""
    for step in data.minutely:
        if step.precip_rate and step.time:
            return dt_util.parse_datetime(step.time)
    return None


# Foreca reports forecast confidence as a single letter.
CONFIDENCE_OPTIONS = {"g": "good", "y": "normal", "o": "low"}


def _confidence(data: ForecaWeatherData) -> str | None:
    """Map Foreca's confidence letter to a readable option."""
    if not data.daily or data.daily[0].confidence is None:
        return None
    return CONFIDENCE_OPTIONS.get(data.daily[0].confidence)


def _daily_aqi(day: int) -> Callable[[ForecaWeatherData], float | str | None]:
    """Read the air quality index for a forecast day."""

    def value_fn(data: ForecaWeatherData) -> float | str | None:
        if len(data.air_quality_daily) <= day:
            return None
        return data.air_quality_daily[day].aqi

    return value_fn


SENSORS: tuple[ForecaSensorDescription, ...] = (
    ForecaSensorDescription(
        key="thunderstorm_probability",
        translation_key="thunderstorm_probability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_current(lambda current: current.thunder_prob),
    ),
    ForecaSensorDescription(
        key="precipitation_intensity",
        suggested_display_precision=1,
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_current(lambda current: current.precip_rate),
    ),
    ForecaSensorDescription(
        key="precipitation_type",
        translation_key="precipitation_type",
        device_class=SensorDeviceClass.ENUM,
        options=["rain", "mixed", "snow"],
        value_fn=_this_hour(lambda hour: hour.precip_type),
    ),
    ForecaSensorDescription(
        key="solar_radiation",
        suggested_display_precision=0,
        translation_key="solar_radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_this_hour(lambda hour: hour.solar_radiation),
    ),
    ForecaSensorDescription(
        key="snow_depth",
        suggested_display_precision=1,
        translation_key="snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_this_hour(lambda hour: hour.snow_depth),
    ),
    ForecaSensorDescription(
        key="sunshine_duration",
        suggested_display_precision=1,
        translation_key="sunshine_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=_today(lambda day: day.sunhours),
    ),
    ForecaSensorDescription(
        key="forecast_confidence",
        translation_key="forecast_confidence",
        device_class=SensorDeviceClass.ENUM,
        options=["good", "normal", "low"],
        value_fn=_confidence,
    ),
    ForecaSensorDescription(
        key="solar_radiation_today",
        translation_key="solar_radiation_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        suggested_display_precision=0,
        value_fn=_today(lambda day: day.solar_radiation_sum),
    ),
    ForecaSensorDescription(
        key="snow_accumulation_today",
        translation_key="snow_accumulation_today",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        suggested_display_precision=1,
        value_fn=_today(lambda day: day.snow_accum),
    ),
    ForecaSensorDescription(
        key="precipitation_forecast_average",
        suggested_display_precision=1,
        translation_key="precipitation_forecast_average",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=_nowcast_average,
    ),
    ForecaSensorDescription(
        key="precipitation_forecast_total",
        suggested_display_precision=1,
        translation_key="precipitation_forecast_total",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        value_fn=_nowcast_total,
    ),
    ForecaSensorDescription(
        key="precipitation_start",
        translation_key="precipitation_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_nowcast_start,
    ),
    ForecaSensorDescription(
        key="api_requests_today",
        translation_key="api_requests_today",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: (
            None
            if data.usage is None
            else data.usage.hits_on(dt_util.utcnow().strftime("%Y-%m-%d"))
        ),
    ),
    ForecaSensorDescription(
        key="api_requests_this_month",
        translation_key="api_requests_this_month",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: None if data.usage is None else data.usage.hits,
    ),
    ForecaSensorDescription(
        key="observation_station",
        translation_key="observation_station",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_observed(lambda obs: obs.station),
    ),
    ForecaSensorDescription(
        key="observed_temperature",
        suggested_display_precision=1,
        translation_key="observed_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_observed(lambda obs: obs.temperature),
    ),
    ForecaSensorDescription(
        key="observed_humidity",
        suggested_display_precision=0,
        translation_key="observed_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_observed(lambda obs: obs.rel_humidity),
    ),
    ForecaSensorDescription(
        key="observed_pressure",
        suggested_display_precision=0,
        translation_key="observed_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_observed(lambda obs: obs.pressure),
    ),
    ForecaSensorDescription(
        key="observed_wind_speed",
        suggested_display_precision=1,
        translation_key="observed_wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_observed(lambda obs: obs.wind_speed),
    ),
    ForecaSensorDescription(
        key="observed_wind_gust_speed",
        suggested_display_precision=1,
        translation_key="observed_wind_gust_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.METERS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_observed(lambda obs: obs.wind_gust),
    ),
    ForecaSensorDescription(
        key="observed_snow_depth",
        suggested_display_precision=1,
        translation_key="observed_snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_observed(lambda obs: obs.snow_depth),
    ),
    ForecaSensorDescription(
        key="aqi",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_nowcast(lambda aq: aq.aqi),
    ),
    ForecaSensorDescription(
        key="dominant_pollutant",
        translation_key="dominant_pollutant",
        value_fn=_nowcast(lambda aq: aq.pollutant),
    ),
    *(
        ForecaSensorDescription(
            key=f"aqi_day_{day}",
            translation_key="aqi_day",
            translation_placeholders={"forecast_day": str(day)},
            device_class=SensorDeviceClass.AQI,
            value_fn=_daily_aqi(day),
        )
        for day in AQ_FORECAST_DAYS
    ),
    ForecaSensorDescription(
        key="aqi_co",
        translation_key="aqi_co",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_co),
    ),
    ForecaSensorDescription(
        key="aqi_no2",
        translation_key="aqi_no2",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_no2),
    ),
    ForecaSensorDescription(
        key="aqi_o3",
        translation_key="aqi_o3",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_o3),
    ),
    ForecaSensorDescription(
        key="aqi_so2",
        translation_key="aqi_so2",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_so2),
    ),
    ForecaSensorDescription(
        key="aqi_pm10",
        translation_key="aqi_pm10",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_pm10),
    ),
    ForecaSensorDescription(
        key="aqi_pm2p5",
        translation_key="aqi_pm2p5",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=_nowcast(lambda aq: aq.aqi_pm2p5),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ForecaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Foreca air quality sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        ForecaAirQualitySensor(coordinator, entry, description)
        for description in SENSORS
    )


class ForecaAirQualitySensor(ForecaEntity, SensorEntity):
    """Define a Foreca air quality sensor."""

    entity_description: ForecaSensorDescription

    def __init__(
        self,
        coordinator: ForecaUpdateCoordinator,
        entry: ForecaConfigEntry,
        description: ForecaSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}-{description.key}"

    @property
    @override
    def available(self) -> bool:
        """Return if the sensor has a value."""
        return (
            super().available
            and self.entity_description.value_fn(self.coordinator.data) is not None
        )

    @property
    @override
    def native_value(self) -> float | str | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
