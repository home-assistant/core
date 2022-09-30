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
    LENGTH_FEET,
    LENGTH_INCHES,
    LENGTH_METERS,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    TIME_HOURS,
    UV_INDEX,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AccuWeatherDataUpdateCoordinator
from .const import (
    API_IMPERIAL,
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

    value_fn: Callable[[dict[str, Any], str], StateType]


@dataclass
class AccuWeatherSensorDescription(
    SensorEntityDescription, AccuWeatherSensorDescriptionMixin
):
    """Class describing AccuWeather sensor entities."""

    attr_fn: Callable[[dict[str, Any]], dict[str, StateType]] = lambda _: {}
    unit_fn: Callable[[bool], str | None] = lambda _: None


FORECAST_SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="CloudCoverDay",
        icon="mdi:weather-cloudy",
        name="Cloud cover day",
        entity_registry_enabled_default=False,
        unit_fn=lambda _: PERCENTAGE,
        value_fn=lambda data, _: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverNight",
        icon="mdi:weather-cloudy",
        name="Cloud cover night",
        entity_registry_enabled_default=False,
        unit_fn=lambda _: PERCENTAGE,
        value_fn=lambda data, _: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="Grass",
        icon="mdi:grass",
        name="Grass pollen",
        entity_registry_enabled_default=False,
        unit_fn=lambda _: CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="HoursOfSun",
        icon="mdi:weather-partly-cloudy",
        name="Hours of sun",
        unit_fn=lambda _: TIME_HOURS,
        value_fn=lambda data, _: cast(float, data),
    ),
    AccuWeatherSensorDescription(
        key="Mold",
        icon="mdi:blur",
        name="Mold pollen",
        entity_registry_enabled_default=False,
        unit_fn=lambda _: CONCENTRATION_PARTS_PER_CUBIC_METER,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="Ozone",
        icon="mdi:vector-triangle",
        name="Ozone",
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="Ragweed",
        icon="mdi:sprout",
        name="Ragweed pollen",
        unit_fn=lambda _: CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature max",
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, _: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature min",
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, _: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade max",
        entity_registry_enabled_default=False,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, _: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade min",
        entity_registry_enabled_default=False,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, _: cast(float, data[ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityDay",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability day",
        unit_fn=lambda _: PERCENTAGE,
        value_fn=lambda data, _: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityNight",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability night",
        unit_fn=lambda _: PERCENTAGE,
        value_fn=lambda data, _: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="Tree",
        icon="mdi:tree-outline",
        name="Tree pollen",
        unit_fn=lambda _: CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        unit_fn=lambda _: UV_INDEX,
        value_fn=lambda data, _: cast(int, data[ATTR_VALUE]),
        attr_fn=lambda data: {ATTR_LEVEL: data[ATTR_CATEGORY]},
    ),
    AccuWeatherSensorDescription(
        key="WindGustDay",
        icon="mdi:weather-windy",
        name="Wind gust day",
        entity_registry_enabled_default=False,
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, _: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindGustNight",
        icon="mdi:weather-windy",
        name="Wind gust night",
        entity_registry_enabled_default=False,
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, _: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindDay",
        icon="mdi:weather-windy",
        name="Wind day",
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, _: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
        attr_fn=lambda data: {"direction": data[ATTR_DIRECTION][ATTR_ENGLISH]},
    ),
    AccuWeatherSensorDescription(
        key="WindNight",
        icon="mdi:weather-windy",
        name="Wind night",
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, _: cast(float, data[ATTR_SPEED][ATTR_VALUE]),
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
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Ceiling",
        icon="mdi:weather-fog",
        name="Cloud ceiling",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: LENGTH_METERS if metric else LENGTH_FEET,
        value_fn=lambda data, unit: round(data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="CloudCover",
        icon="mdi:weather-cloudy",
        name="Cloud cover",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda _: PERCENTAGE,
        value_fn=lambda data, _: cast(int, data),
    ),
    AccuWeatherSensorDescription(
        key="DewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Dew point",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShade",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Precipitation",
        icon="mdi:weather-rainy",
        name="Precipitation",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: LENGTH_MILLIMETERS if metric else LENGTH_INCHES,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
        attr_fn=lambda data: {"type": data["PrecipitationType"]},
    ),
    AccuWeatherSensorDescription(
        key="PressureTendency",
        device_class="accuweather__pressure_tendency",
        icon="mdi:gauge",
        name="Pressure tendency",
        value_fn=lambda data, _: cast(str, data["LocalizedText"]).lower(),
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda _: UV_INDEX,
        value_fn=lambda data, _: cast(int, data),
        attr_fn=lambda data: {ATTR_LEVEL: data["UVIndexText"]},
    ),
    AccuWeatherSensorDescription(
        key="WetBulbTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wet bulb temperature",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="WindChillTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wind chill temperature",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: TEMP_CELSIUS if metric else TEMP_FAHRENHEIT,
        value_fn=lambda data, unit: cast(float, data[unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="Wind",
        icon="mdi:weather-windy",
        name="Wind",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, unit: cast(float, data[ATTR_SPEED][unit][ATTR_VALUE]),
    ),
    AccuWeatherSensorDescription(
        key="WindGust",
        icon="mdi:weather-windy",
        name="Wind gust",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda metric: SPEED_KILOMETERS_PER_HOUR
        if metric
        else SPEED_MILES_PER_HOUR,
        value_fn=lambda data, unit: cast(float, data[ATTR_SPEED][unit][ATTR_VALUE]),
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
            AccuWeatherForecastSensor(coordinator, description, forecast_day=day)
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
        if self.coordinator.hass.config.units.is_metric:
            self._unit_system = API_METRIC
        else:
            self._unit_system = API_IMPERIAL
        self._attr_native_unit_of_measurement = self.entity_description.unit_fn(
            self.coordinator.hass.config.units.is_metric
        )
        self._attr_device_info = coordinator.device_info
        if forecast_day is not None:
            self.forecast_day = forecast_day

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        return self.entity_description.value_fn(self._sensor_data, self._unit_system)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.entity_description.attr_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = _get_sensor_data(
            self.coordinator.data, self.entity_description.key
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
        return sensors["PrecipitationSummary"][kind]

    return sensors[kind]


class AccuWeatherForecastSensor(AccuWeatherSensor):
    """Define an AccuWeather forecast entity."""

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.entity_description.attr_fn(self._sensor_data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = _get_sensor_data(
            self.coordinator.data, self.entity_description.key, self.forecast_day
        )
        self.async_write_ha_state()
