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
        name="Air quality",
        value_fn=lambda data: cast(str, data[ATTR_CATEGORY]),
        device_class=SensorDeviceClass.ENUM,
        options=["good", "hazardous", "high", "low", "moderate", "unhealthy"],
        translation_key="air_quality",
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverDay",
        icon="mdi:weather-cloudy",
        name="Cloud cover day",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverNight",
        icon="mdi:weather-cloudy",
        name="Cloud cover night",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="Grass",
        icon="mdi:grass",
        name="Grass pollen",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        translation_key="grass_pollen",
    ),
    AccuWeatherSensorDescription(
        key="HoursOfSun",
        icon="mdi:weather-partly-cloudy",
        name="Hours of sun",
        native_unit_of_measurement=UnitOfTime.HOURS,
        value_fn=lambda data: cast(float, data),
    ),
    AccuWeatherSensorDescription(
        key="LongPhraseDay",
        name="Condition day",
        value_fn=lambda data: cast(str, data),
    ),
    AccuWeatherSensorDescription(
        key="LongPhraseNight",
        name="Condition night",
        value_fn=lambda data: cast(str, data),
    ),
    AccuWeatherSensorDescription(
        key="Mold",
        icon="mdi:blur",
        name="Mold pollen",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        translation_key="mold_pollen",
    ),
    AccuWeatherSensorDescription(
        key="Ragweed",
        icon="mdi:sprout",
        name="Ragweed pollen",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        translation_key="ragweed_pollen",
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature max",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature min",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade max",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade min",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="SolarIrradianceDay",
        icon="mdi:weather-sunny",
        name="Solar irradiance day",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="SolarIrradianceNight",
        icon="mdi:weather-sunny",
        name="Solar irradiance night",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfIrradiance.WATTS_PER_SQUARE_METER,
        value_fn=lambda data: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityDay",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability day",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityNight",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability night",
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="Tree",
        icon="mdi:tree-outline",
        name="Tree pollen",
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        translation_key="tree_pollen",
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
        translation_key="uv_index",
    ),
    AccuWeatherSensorDescription(
        key="WindGustDay",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind gust day",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindGustNight",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind gust night",
        entity_registry_enabled_default=False,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindDay",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind day",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindNight",
        device_class=SensorDeviceClass.WIND_SPEED,
        name="Wind night",
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
