"""Support for the AccuWeather service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
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

from . import AccuWeatherDataUpdateCoordinator
from .const import (
    API_METRIC,
    ATTR_CATEGORY,
    ATTR_DIRECTION,
    ATTR_ENGLISH,
    ATTR_FORECAST,
    ATTR_LEVEL,
    ATTR_SPEED,
    ATTR_VALUE,
    ATTRIBUTION,
    DOMAIN,
    MAX_FORECAST_DAYS,
)

PARALLEL_UPDATES = 1


@dataclass
class AccuWeatherSensorDescriptionMixin:
    """Mixin for AccuWeather sensor."""

    value_fn: Callable[[dict[str, Any]], str | int | float | None]


@dataclass
class AccuWeatherSensorDescription(
    SensorEntityDescription, AccuWeatherSensorDescriptionMixin
):
    """Class describing AccuWeather sensor entities."""

    attr_fn: Callable[[dict[str, Any]], dict[str, Any]] = lambda _: {}


FORECAST_SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="AirQuality",
        icon="mdi:air-filter",
        value_fn=lambda data: cast(str, data[ATTR_CATEGORY]),
        device_class=SensorDeviceClass.ENUM,
        options=["good", "hazardous", "high", "low", "moderate", "unhealthy"],
        _translation_key="air_quality",
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverDay",
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
        _translation_key="cloud_cover",
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverNight",
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
        _translation_key="cloud_cover",
    ),
    AccuWeatherSensorDescription(
        key="Grass",
        icon="mdi:grass",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        _translation_key="grass_pollen",
    ),
    AccuWeatherSensorDescription(
        key="HoursOfSun",
        icon="mdi:weather-partly-cloudy",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: cast(float, data),
        _translation_key="hours_of_sun",
    ),
    AccuWeatherSensorDescription(
        key="LongPhraseDay",
        value_fn=lambda data: cast(str, data),
        _translation_key="condition_day",
    ),
    AccuWeatherSensorDescription(
        key="LongPhraseNight",
        value_fn=lambda data: cast(str, data),
        _translation_key="condition_night",
    ),
    AccuWeatherSensorDescription(
        key="Mold",
        icon="mdi:blur",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        _translation_key="mold_pollen",
    ),
    AccuWeatherSensorDescription(
        key="Ragweed",
        icon="mdi:sprout",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        _translation_key="ragweed_pollen",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="realfeel_temperature_max",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="realfeel_temperature_min",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="realfeel_temperature_shade_max",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="realfeel_temperature_shade_min",
    ),
    AccuWeatherSensorDescription(
        key="SolarIrradianceDay",
        icon="mdi:weather-sunny",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="solar_irradiance_day",
    ),
    AccuWeatherSensorDescription(
        key="SolarIrradianceNight",
        icon="mdi:weather-sunny",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
        _translation_key="solar_irradiance_night",
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityDay",
        icon="mdi:weather-lightning",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
        _translation_key="thunderstorm_probability_day",
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityNight",
        icon="mdi:weather-lightning",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
        _translation_key="thunderstorm_probability_night",
    ),
    AccuWeatherSensorDescription(
        key="Tree",
        icon="mdi:tree-outline",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        _translation_key="tree_pollen",
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        _translation_key="uv_index",
    ),
    AccuWeatherSensorDescription(
        key="WindGustDay",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
        _translation_key="wind_gust_day",
    ),
    AccuWeatherSensorDescription(
        key="WindGustNight",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
        _translation_key="wind_gust_night",
    ),
    AccuWeatherSensorDescription(
        key="WindDay",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
        _translation_key="wind_speed_day",
    ),
    AccuWeatherSensorDescription(
        key="WindNight",
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
        _translation_key="wind_speed_night",
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
        translation_key="wind",
    ),
    AccuWeatherSensorDescription(
        key="WindGust",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][API_METRIC][ATTR_VALUE]),
        translation_key="wind_gust",
    ),
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add AccuWeather entities from a config_entry."""

    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = [
        AccuWeatherSensor(coordinator, description) for description in SENSOR_TYPES
    ]

    if coordinator.forecast:
        # Some air quality/allergy sensors are only available for certain
        # locations.
        sensors.extend(
            AccuWeatherSensor(coordinator, description, forecast_day=day)
            for day in range(MAX_FORECAST_DAYS + 1)
            for description in FORECAST_SENSOR_TYPES
            if description.key in coordinator.data[ATTR_FORECAST][0]
        )

    async_add_entities(sensors)


class AccuWeatherSensor(
    CoordinatorEntity[AccuWeatherDataUpdateCoordinator], SensorEntity
):
    """Define an AccuWeather entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    entity_description: AccuWeatherSensorDescription

    def __init__(
        self,
        coordinator: AccuWeatherDataUpdateCoordinator,
        description: AccuWeatherSensorDescription,
        forecast_day: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_data = _get_sensor_data(
            coordinator.data, description.key, forecast_day
        )
        if forecast_day is not None:
            self._attr_name = f"{description.name} {forecast_day}d"
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}-{forecast_day}".lower()
            )
            self._attr_translation_key = (
                f"{description._translation_key}_{forecast_day}d"
            )
            _LOGGER.warning(f"{description._translation_key}_{forecast_day}d")
        else:
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}".lower()
            )
        self._attr_device_info = coordinator.device_info
        self.forecast_day = forecast_day

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self._sensor_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.forecast_day is not None:
            return self.entity_description.attr_fn(self._sensor_data)

        return self.entity_description.attr_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = _get_sensor_data(
            self.coordinator.data, self.entity_description.key, self.forecast_day
        )
        self.async_write_ha_state()


def _get_sensor_data(
    sensors: dict[str, Any],
    kind: str,
    forecast_day: int | None = None,
) -> Any:
    """Get sensor data."""
    if forecast_day is not None:
        return sensors[ATTR_FORECAST][forecast_day][kind]

    if kind == "Precipitation":
        return sensors["PrecipitationSummary"]["PastHour"]

    return sensors[kind]
