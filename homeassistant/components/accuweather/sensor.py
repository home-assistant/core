"""Support for the AccuWeather service."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_CUBIC_METER,
    PERCENTAGE,
    UV_INDEX,
    UnitOfIrradiance,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AccuWeatherData
from .const import (
    API_METRIC,
    ATTR_CATEGORY,
    ATTR_DIRECTION,
    ATTR_ENGLISH,
    ATTR_LEVEL,
    ATTR_SPEED,
    ATTR_VALUE,
    ATTRIBUTION,
    DOMAIN,
    MAX_FORECAST_DAYS,
)
from .coordinator import (
    AccuWeatherDailyForecastDataUpdateCoordinator,
    AccuWeatherObservationDataUpdateCoordinator,
)

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class AccuWeatherSensorDescription(SensorEntityDescription):
    """Class describing AccuWeather sensor entities."""

    value_fn: Callable[[dict[str, Any]], str | int | float | None]
    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] = lambda _: {}


@dataclass(frozen=True, kw_only=True)
class AccuWeatherForecastSensorDescription(AccuWeatherSensorDescription):
    """Class describing AccuWeather sensor entities."""

    day: int


FORECAST_SENSOR_TYPES: tuple[AccuWeatherForecastSensorDescription, ...] = (
    *(
        AccuWeatherForecastSensorDescription(
            key="AirQuality",
            icon="mdi:air-filter",
            value_fn=lambda data: cast(str, data[ATTR_CATEGORY]),
            device_class=SensorDeviceClass.ENUM,
            options=["good", "hazardous", "high", "low", "moderate", "unhealthy"],
            translation_key=f"air_quality_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="CloudCoverDay",
            icon="mdi:weather-cloudy",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(int, data),
            translation_key=f"cloud_cover_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="CloudCoverNight",
            icon="mdi:weather-cloudy",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(int, data),
            translation_key=f"cloud_cover_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="Grass",
            icon="mdi:grass",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            value_fn=lambda data: cast(int, data[ATTR_VALUE]),
            attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
            translation_key=f"grass_pollen_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="HoursOfSun",
            icon="mdi:weather-partly-cloudy",
            native_unit_of_measurement=UnitOfTime.HOURS,
            value_fn=lambda data: cast(float, data),
            translation_key=f"hours_of_sun_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="LongPhraseDay",
            value_fn=lambda data: cast(str, data),
            translation_key=f"condition_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="LongPhraseNight",
            value_fn=lambda data: cast(str, data),
            translation_key=f"condition_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="Mold",
            icon="mdi:blur",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            value_fn=lambda data: cast(int, data[ATTR_VALUE]),
            attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
            translation_key=f"mold_pollen_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="Ragweed",
            icon="mdi:sprout",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
            value_fn=lambda data: cast(int, data[ATTR_VALUE]),
            attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
            translation_key=f"ragweed_pollen_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="RealFeelTemperatureMax",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"realfeel_temperature_max_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="RealFeelTemperatureMin",
            device_class=SensorDeviceClass.TEMPERATURE,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"realfeel_temperature_min_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="RealFeelTemperatureShadeMax",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"realfeel_temperature_shade_max_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="RealFeelTemperatureShadeMin",
            device_class=SensorDeviceClass.TEMPERATURE,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"realfeel_temperature_shade_min_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="SolarIrradianceDay",
            icon="mdi:weather-sunny",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"solar_irradiance_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="SolarIrradianceNight",
            icon="mdi:weather-sunny",
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
            value_fn=lambda data: cast(float, data[ATTR_VALUE]),
            translation_key=f"solar_irradiance_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="ThunderstormProbabilityDay",
            icon="mdi:weather-lightning",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(int, data),
            translation_key=f"thunderstorm_probability_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="ThunderstormProbabilityNight",
            icon="mdi:weather-lightning",
            native_unit_of_measurement=PERCENTAGE,
            value_fn=lambda data: cast(int, data),
            translation_key=f"thunderstorm_probability_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="Tree",
            icon="mdi:tree-outline",
            native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
            entity_registry_enabled_default=False,
            value_fn=lambda data: cast(int, data[ATTR_VALUE]),
            attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
            translation_key=f"tree_pollen_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="UVIndex",
            icon="mdi:weather-sunny",
            native_unit_of_measurement=UV_INDEX,
            value_fn=lambda data: cast(int, data[ATTR_VALUE]),
            attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
            translation_key=f"uv_index_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="WindGustDay",
            device_class=SensorDeviceClass.WIND_SPEED,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
            attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
            translation_key=f"wind_gust_speed_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="WindGustNight",
            device_class=SensorDeviceClass.WIND_SPEED,
            entity_registry_enabled_default=False,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
            attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
            translation_key=f"wind_gust_speed_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="WindDay",
            device_class=SensorDeviceClass.WIND_SPEED,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
            attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
            translation_key=f"wind_speed_day_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
    *(
        AccuWeatherForecastSensorDescription(
            key="WindNight",
            device_class=SensorDeviceClass.WIND_SPEED,
            native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
            value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
            attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
            translation_key=f"wind_speed_night_{day}d",
            day=day,
        )
        for day in range(MAX_FORECAST_DAYS + 1)
    ),
)

SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="ApparentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="apparent_temperature",
    ),
    AccuWeatherSensorDescription(
        key="Ceiling",
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:weather-fog",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        suggested_display_precision=0,
        translation_key="cloud_ceiling",
    ),
    AccuWeatherSensorDescription(
        key="CloudCover",
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
        translation_key="cloud_cover",
    ),
    AccuWeatherSensorDescription(
        key="DewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="dew_point",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="realfeel_temperature",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShade",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="realfeel_temperature_shade",
    ),
    AccuWeatherSensorDescription(
        key="Precipitation",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        attr_fn=lambda data: {"type": data["PrecipitationType"]},
        translation_key="precipitation",
    ),
    AccuWeatherSensorDescription(
        key="PressureTendency",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:gauge",
        options=["falling", "rising", "steady"],
        value_fn=lambda data: cast(str, data["LocalizedText"]).lower(),
        translation_key="pressure_tendency",
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data),
        attr_fn=lambda data: {ATTR_LEVEL: data["UVIndexText"]},
        translation_key="uv_index",
    ),
    AccuWeatherSensorDescription(
        key="WetBulbTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="wet_bulb_temperature",
    ),
    AccuWeatherSensorDescription(
        key="WindChillTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        translation_key="wind_chill_temperature",
    ),
    AccuWeatherSensorDescription(
        key="Wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][API_METRIC][ATTR_VALUE]),
        translation_key="wind_speed",
    ),
    AccuWeatherSensorDescription(
        key="WindGust",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][API_METRIC][ATTR_VALUE]),
        translation_key="wind_gust_speed",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add AccuWeather entities from a config_entry."""

    accuweather_data: AccuWeatherData = hass.data[DOMAIN][entry.entry_id]

    observation_coordinator: AccuWeatherObservationDataUpdateCoordinator = (
        accuweather_data.coordinator_observation
    )
    forecast_daily_coordinator: AccuWeatherDailyForecastDataUpdateCoordinator = (
        accuweather_data.coordinator_daily_forecast
    )

    sensors: list[AccuWeatherSensor | AccuWeatherForecastSensor] = [
        AccuWeatherSensor(observation_coordinator, description)
        for description in SENSOR_TYPES
    ]

    sensors.extend(
        [
            AccuWeatherForecastSensor(forecast_daily_coordinator, description)
            for description in FORECAST_SENSOR_TYPES
            if description.key in forecast_daily_coordinator.data[description.day]
        ]
    )

    async_add_entities(sensors)


class AccuWeatherSensor(
    CoordinatorEntity[AccuWeatherObservationDataUpdateCoordinator], SensorEntity
):
    """Define an AccuWeather entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: AccuWeatherSensorDescription

    def __init__(
        self,
        coordinator: AccuWeatherObservationDataUpdateCoordinator,
        description: AccuWeatherSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.entity_description = description
        self._sensor_data = self._get_sensor_data(coordinator.data, description.key)
        self._attr_unique_id = f"{coordinator.location_key}-{description.key}".lower()
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self._sensor_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.entity_description.attr_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self._get_sensor_data(
            self.coordinator.data, self.entity_description.key
        )
        self.async_write_ha_state()

    @staticmethod
    def _get_sensor_data(
        sensors: dict[str, Any],
        kind: str,
    ) -> Any:
        """Get sensor data."""
        if kind == "Precipitation":
            return sensors["PrecipitationSummary"]["PastHour"]

        return sensors[kind]


class AccuWeatherForecastSensor(
    CoordinatorEntity[AccuWeatherDailyForecastDataUpdateCoordinator], SensorEntity
):
    """Define an AccuWeather entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: AccuWeatherForecastSensorDescription

    def __init__(
        self,
        coordinator: AccuWeatherDailyForecastDataUpdateCoordinator,
        description: AccuWeatherForecastSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.forecast_day = description.day
        self.entity_description = description
        self._sensor_data = self._get_sensor_data(
            coordinator.data, description.key, self.forecast_day
        )
        self._attr_unique_id = (
            f"{coordinator.location_key}-{description.key}-{self.forecast_day}".lower()
        )
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self._sensor_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.entity_description.attr_fn(self._sensor_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = self._get_sensor_data(
            self.coordinator.data, self.entity_description.key, self.forecast_day
        )
        self.async_write_ha_state()

    @staticmethod
    def _get_sensor_data(
        sensors: list[dict[str, Any]],
        kind: str,
        forecast_day: int,
    ) -> Any:
        """Get sensor data."""
        return sensors[forecast_day][kind]
