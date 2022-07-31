"""Support for the AccuWeather service."""
from __future__ import annotations

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
    ATTR_FORECAST,
    ATTRIBUTION,
    DOMAIN,
    MAX_FORECAST_DAYS,
)

PARALLEL_UPDATES = 1


@dataclass
class AccuWeatherSensorDescription(SensorEntityDescription):
    """Class describing AccuWeather sensor entities."""

    unit_metric: str | None = None
    unit_imperial: str | None = None


FORECAST_SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="CloudCoverDay",
        icon="mdi:weather-cloudy",
        name="Cloud cover day",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="CloudCoverNight",
        icon="mdi:weather-cloudy",
        name="Cloud cover night",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="Grass",
        icon="mdi:grass",
        name="Grass pollen",
        unit_metric=CONCENTRATION_PARTS_PER_CUBIC_METER,
        unit_imperial=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="HoursOfSun",
        icon="mdi:weather-partly-cloudy",
        name="Hours of sun",
        unit_metric=TIME_HOURS,
        unit_imperial=TIME_HOURS,
    ),
    AccuWeatherSensorDescription(
        key="Mold",
        icon="mdi:blur",
        name="Mold pollen",
        unit_metric=CONCENTRATION_PARTS_PER_CUBIC_METER,
        unit_imperial=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="Ozone",
        icon="mdi:vector-triangle",
        name="Ozone",
        unit_metric=None,
        unit_imperial=None,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="Ragweed",
        icon="mdi:sprout",
        name="Ragweed pollen",
        unit_metric=CONCENTRATION_PARTS_PER_CUBIC_METER,
        unit_imperial=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature max",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature min",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMax",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade max",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShadeMin",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade min",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityDay",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability day",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
    ),
    AccuWeatherSensorDescription(
        key="ThunderstormProbabilityNight",
        icon="mdi:weather-lightning",
        name="Thunderstorm probability night",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
    ),
    AccuWeatherSensorDescription(
        key="Tree",
        icon="mdi:tree-outline",
        name="Tree pollen",
        unit_metric=CONCENTRATION_PARTS_PER_CUBIC_METER,
        unit_imperial=CONCENTRATION_PARTS_PER_CUBIC_METER,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        unit_metric=UV_INDEX,
        unit_imperial=UV_INDEX,
    ),
    AccuWeatherSensorDescription(
        key="WindGustDay",
        icon="mdi:weather-windy",
        name="Wind gust day",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="WindGustNight",
        icon="mdi:weather-windy",
        name="Wind gust night",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
        entity_registry_enabled_default=False,
    ),
    AccuWeatherSensorDescription(
        key="WindDay",
        icon="mdi:weather-windy",
        name="Wind day",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
    ),
    AccuWeatherSensorDescription(
        key="WindNight",
        icon="mdi:weather-windy",
        name="Wind night",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
    ),
)

SENSOR_TYPES: tuple[AccuWeatherSensorDescription, ...] = (
    AccuWeatherSensorDescription(
        key="ApparentTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Apparent temperature",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="Ceiling",
        icon="mdi:weather-fog",
        name="Cloud ceiling",
        unit_metric=LENGTH_METERS,
        unit_imperial=LENGTH_FEET,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="CloudCover",
        icon="mdi:weather-cloudy",
        name="Cloud cover",
        unit_metric=PERCENTAGE,
        unit_imperial=PERCENTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="DewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Dew point",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="RealFeelTemperatureShade",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="RealFeel temperature shade",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="Precipitation",
        icon="mdi:weather-rainy",
        name="Precipitation",
        unit_metric=LENGTH_MILLIMETERS,
        unit_imperial=LENGTH_INCHES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="PressureTendency",
        device_class="accuweather__pressure_tendency",
        icon="mdi:gauge",
        name="Pressure tendency",
        unit_metric=None,
        unit_imperial=None,
    ),
    AccuWeatherSensorDescription(
        key="UVIndex",
        icon="mdi:weather-sunny",
        name="UV index",
        unit_metric=UV_INDEX,
        unit_imperial=UV_INDEX,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="WetBulbTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wet bulb temperature",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="WindChillTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        name="Wind chill temperature",
        unit_metric=TEMP_CELSIUS,
        unit_imperial=TEMP_FAHRENHEIT,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="Wind",
        icon="mdi:weather-windy",
        name="Wind",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AccuWeatherSensorDescription(
        key="WindGust",
        icon="mdi:weather-windy",
        name="Wind gust",
        unit_metric=SPEED_KILOMETERS_PER_HOUR,
        unit_imperial=SPEED_MILES_PER_HOUR,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add AccuWeather entities from a config_entry."""

    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[AccuWeatherSensor] = []
    for description in SENSOR_TYPES:
        sensors.append(AccuWeatherSensor(coordinator, description))

    if coordinator.forecast:
        for description in FORECAST_SENSOR_TYPES:
            for day in range(MAX_FORECAST_DAYS + 1):
                # Some air quality/allergy sensors are only available for certain
                # locations.
                if description.key in coordinator.data[ATTR_FORECAST][0]:
                    sensors.append(
                        AccuWeatherSensor(coordinator, description, forecast_day=day)
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
            coordinator.data, forecast_day, description.key
        )
        self._attrs: dict[str, Any] = {}
        if forecast_day is not None:
            self._attr_name = f"{description.name} {forecast_day}d"
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}-{forecast_day}".lower()
            )
        else:
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}".lower()
            )
        if coordinator.is_metric:
            self._unit_system = API_METRIC
            self._attr_native_unit_of_measurement = description.unit_metric
        else:
            self._unit_system = API_IMPERIAL
            self._attr_native_unit_of_measurement = description.unit_imperial
        self._attr_device_info = coordinator.device_info
        self.forecast_day = forecast_day

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.forecast_day is not None:
            if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
                return cast(float, self._sensor_data["Value"])
            if self.entity_description.key == "UVIndex":
                return cast(int, self._sensor_data["Value"])
        if self.entity_description.key in ("Grass", "Mold", "Ragweed", "Tree", "Ozone"):
            return cast(int, self._sensor_data["Value"])
        if self.entity_description.key == "Ceiling":
            return round(self._sensor_data[self._unit_system]["Value"])
        if self.entity_description.key == "PressureTendency":
            return cast(str, self._sensor_data["LocalizedText"].lower())
        if self.entity_description.device_class == SensorDeviceClass.TEMPERATURE:
            return cast(float, self._sensor_data[self._unit_system]["Value"])
        if self.entity_description.key == "Precipitation":
            return cast(float, self._sensor_data[self._unit_system]["Value"])
        if self.entity_description.key in ("Wind", "WindGust"):
            return cast(float, self._sensor_data["Speed"][self._unit_system]["Value"])
        if self.entity_description.key in (
            "WindDay",
            "WindNight",
            "WindGustDay",
            "WindGustNight",
        ):
            return cast(StateType, self._sensor_data["Speed"]["Value"])
        return cast(StateType, self._sensor_data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.forecast_day is not None:
            if self.entity_description.key in (
                "WindDay",
                "WindNight",
                "WindGustDay",
                "WindGustNight",
            ):
                self._attrs["direction"] = self._sensor_data["Direction"]["English"]
            elif self.entity_description.key in (
                "Grass",
                "Mold",
                "Ozone",
                "Ragweed",
                "Tree",
                "UVIndex",
            ):
                self._attrs["level"] = self._sensor_data["Category"]
            return self._attrs
        if self.entity_description.key == "UVIndex":
            self._attrs["level"] = self.coordinator.data["UVIndexText"]
        elif self.entity_description.key == "Precipitation":
            self._attrs["type"] = self.coordinator.data["PrecipitationType"]
        return self._attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self._sensor_data = _get_sensor_data(
            self.coordinator.data, self.forecast_day, self.entity_description.key
        )
        self.async_write_ha_state()


def _get_sensor_data(
    sensors: dict[str, Any], forecast_day: int | None, kind: str
) -> Any:
    """Get sensor data."""
    if forecast_day is not None:
        return sensors[ATTR_FORECAST][forecast_day][kind]

    if kind == "Precipitation":
        return sensors["PrecipitationSummary"][kind]

    return sensors[kind]
