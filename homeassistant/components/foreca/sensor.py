"""Sensor platform for the Foreca integration."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from pyforeca import AirQualityForecast, CurrentWeather, DailyForecast, HourlyForecast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator, ForecaWeatherData
from .entity import ForecaEntity

PARALLEL_UPDATES = 0

AQ_FORECAST_DAYS = (1, 2, 3)


@dataclass(frozen=True, kw_only=True)
class ForecaSensorDescription(SensorEntityDescription):
    """Class describing Foreca sensor entities."""

    value_fn: Callable[[ForecaWeatherData], float | str | None]


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
        translation_key="solar_radiation",
        device_class=SensorDeviceClass.IRRADIANCE,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_this_hour(lambda hour: hour.solar_radiation),
    ),
    ForecaSensorDescription(
        key="snow_depth",
        translation_key="snow_depth",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.CENTIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_this_hour(lambda hour: hour.snow_depth),
    ),
    ForecaSensorDescription(
        key="sunshine_duration",
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
    def native_value(self) -> float | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)
