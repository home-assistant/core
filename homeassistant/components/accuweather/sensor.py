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
from homeassistant.helpers.typing import StateType
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

SENSOR_AIR_QUALITY = "air_quality"
SENSOR_CLOUD_COVER_DAY = "cloud_cover_day"
SENSOR_CLOUD_COVER_NIGHT = "cloud_cover_night"
SENSOR_GRASS_POLLEN = "grass_pollen"
SENSOR_HOURS_OF_SUN = "hours_of_sun"
SENSOR_CONDITION_DAY = "condition_day"
SENSOR_CONDITION_NIGHT = "condition_night"
SENSOR_MOLD_POLLEN = "nold_pollen"
SENSOR_RAGWEED_POLLEN = "ragweed_pollen"
SENSOR_REAL_FEEL_TEMPERATURE_MAX = "real_feel_temperature_max"
SENSOR_REAL_FEEL_TEMPERATURE_MIN = "real_feel_temperature_min"
SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MAX = "real_feel_temperature_shade_max"
SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MIN = "real_feel_temperature_shade_min"
SENSOR_SOLAR_IRRADIANCE_DAY = "solar_irradiance_day"
SENSOR_SOLAR_IRRADIANCE_NIGHT = "solar_irradiance_night"
SENSOR_THUNDERSTORM_PROBABILITY_DAY = "thunderstorm_probability_day"
SENSOR_THUNDERSTORM_PROBABILITY_NIGHT = "thunderstorm_probability_night"
SENSOR_TREE_POLLEN = "tree_pollen"
SENSOR_UV_INDEX = "uv_index"
SENSOR_WIND_GUST_DAY = "wind_gust_day"
SENSOR_WIND_GUST_NIGHT = "wind_gust_night"
SENSOR_WIND_DAY = "wind_day"
SENSOR_WIND_NIGHT = "wind_night"


@dataclass
class AccuWeatherSensorDescriptionMixin:
    """Mixin for AccuWeather sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]


@dataclass
class AccuWeatherSensorDescription(
    SensorEntityDescription, AccuWeatherSensorDescriptionMixin
):
    """Class describing AccuWeather sensor entities."""

    attr_fn: Callable[[dict[str, Any]], dict[str, StateType]] = lambda _: {}


FORECAST_SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key=SENSOR_AIR_QUALITY,
        translation_key=SENSOR_AIR_QUALITY,
        icon="mdi:air-filter",
        value_fn=lambda data: cast(str, data[ATTR_CATEGORY]),
        device_class=SensorDeviceClass.ENUM,
        options=["good", "hazardous", "high", "low", "moderate", "unhealthy"],
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_CLOUD_COVER_DAY,
        translation_key=SENSOR_CLOUD_COVER_DAY,
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_CLOUD_COVER_NIGHT,
        translation_key=SENSOR_CLOUD_COVER_NIGHT,
        icon="mdi:weather-cloudy",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_GRASS_POLLEN,
        translation_key=SENSOR_GRASS_POLLEN,
        icon="mdi:grass",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_HOURS_OF_SUN,
        translation_key=SENSOR_HOURS_OF_SUN,
        icon="mdi:weather-partly-cloudy",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: cast(float, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_CONDITION_DAY,
        translation_key=SENSOR_CONDITION_DAY,
        value_fn=lambda data: cast(str, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_CONDITION_NIGHT,
        translation_key=SENSOR_CONDITION_NIGHT,
        value_fn=lambda data: cast(str, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_MOLD_POLLEN,
        translation_key=SENSOR_MOLD_POLLEN,
        icon="mdi:blur",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_RAGWEED_POLLEN,
        translation_key=SENSOR_RAGWEED_POLLEN,
        icon="mdi:sprout",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_REAL_FEEL_TEMPERATURE_MAX,
        translation_key=SENSOR_REAL_FEEL_TEMPERATURE_MAX,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_REAL_FEEL_TEMPERATURE_MIN,
        translation_key=SENSOR_REAL_FEEL_TEMPERATURE_MIN,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MAX,
        translation_key=SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MAX,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MIN,
        translation_key=SENSOR_REAL_FEEL_TEMPERATURE_SHADE_MIN,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_SOLAR_IRRADIANCE_DAY,
        translation_key=SENSOR_SOLAR_IRRADIANCE_DAY,
        icon="mdi:weather-sunny",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_SOLAR_IRRADIANCE_NIGHT,
        translation_key=SENSOR_SOLAR_IRRADIANCE_NIGHT,
        icon="mdi:weather-sunny",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_THUNDERSTORM_PROBABILITY_DAY,
        translation_key=SENSOR_THUNDERSTORM_PROBABILITY_DAY,
        icon="mdi:weather-lightning",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_THUNDERSTORM_PROBABILITY_NIGHT,
        translation_key=SENSOR_THUNDERSTORM_PROBABILITY_NIGHT,
        icon="mdi:weather-lightning",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_TREE_POLLEN,
        translation_key=SENSOR_TREE_POLLEN,
        icon="mdi:tree-outline",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_UV_INDEX,
        translation_key=SENSOR_UV_INDEX,
        icon="mdi:weather-sunny",
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_WIND_GUST_DAY,
        translation_key=SENSOR_WIND_GUST_DAY,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_WIND_GUST_NIGHT,
        translation_key=SENSOR_WIND_GUST_NIGHT,
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_WIND_DAY,
        translation_key=SENSOR_WIND_DAY,
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key=SENSOR_WIND_NIGHT,
        translation_key=SENSOR_WIND_NIGHT,
        device_class=SensorDeviceClass.WIND_SPEED,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
)

SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="ApparentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Apparent temperature",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Ceiling",
        device_class=SensorDeviceClass.DISTANCE,
        icon="mdi:weather-fog",
        name="Cloud ceiling",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        suggested_display_precision=0,
    ),
    AccuWeatherSensorDescription(
        key="CloudCover",
        icon="mdi:weather-cloudy",
        name="Cloud cover",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="DewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Dew point",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShade",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Precipitation",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        name="Precipitation",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
        attr_fn=lambda data: {"type": data["PrecipitationType"]},
    ),
    AccuWeatherSensorDescription(
        key="PressureTendency",
        device_class=SensorDeviceClass.ENUM,
        icon="mdi:gauge",
        name="Pressure tendency",
        options=["falling", "rising", "steady"],
        translation_key="pressure_tendency",
        value_fn=lambda data: cast(str, data["LocalizedText"]).lower(),
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data),
        attr_fn=lambda data: {ATTR_LEVEL: data["UVIndexText"]},
    ),
    AccuWeatherSensorDescription(
        key="WetBulbTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wet bulb temperature",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="WindChillTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wind chill temperature",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Wind",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][API_METRIC][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="WindGust",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind gust",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][API_METRIC][ATTR_VALUE]),
    ),
)


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
        else:
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}".lower()
            )
        self._attr_device_info = coordinator.device_info
        self.forecast_day = forecast_day

    @property
    def native_value(self) -> StateType:
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
