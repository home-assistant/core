"""Support for the AccuWeather service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, DEVICE_CLASS_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
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
    FORECAST_SENSOR_TYPES,
    MANUFACTURER,
    MAX_FORECAST_DAYS,
    NAME,
    SENSOR_TYPES,
)
from .model import AccuWeatherSensorDescription

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add AccuWeather entities from a config_entry."""
    name: str = entry.data[CONF_NAME]

    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    sensors: list[AccuWeatherSensor] = []
    for description in SENSOR_TYPES:
        sensors.append(AccuWeatherSensor(name, coordinator, description))

    if coordinator.forecast:
        for description in FORECAST_SENSOR_TYPES:
            for day in range(MAX_FORECAST_DAYS + 1):
                # Some air quality/allergy sensors are only available for certain
                # locations.
                if description.key in coordinator.data[ATTR_FORECAST][0]:
                    sensors.append(
                        AccuWeatherSensor(
                            name, coordinator, description, forecast_day=day
                        )
                    )

    async_add_entities(sensors)


class AccuWeatherSensor(CoordinatorEntity, SensorEntity):
    """Define an AccuWeather entity."""

    _attr_attribution = ATTRIBUTION
    coordinator: AccuWeatherDataUpdateCoordinator
    entity_description: AccuWeatherSensorDescription

    def __init__(
        self,
        name: str,
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
            self._attr_name = f"{name} {description.name} {forecast_day}d"
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}-{forecast_day}".lower()
            )
        else:
            self._attr_name = f"{name} {description.name}"
            self._attr_unique_id = (
                f"{coordinator.location_key}-{description.key}".lower()
            )
        if coordinator.is_metric:
            self._unit_system = API_METRIC
            self._attr_native_unit_of_measurement = description.unit_metric
        else:
            self._unit_system = API_IMPERIAL
            self._attr_native_unit_of_measurement = description.unit_imperial
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.location_key)},
            manufacturer=MANUFACTURER,
            name=NAME,
        )
        self.forecast_day = forecast_day

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        if self.forecast_day is not None:
            if self.entity_description.device_class == DEVICE_CLASS_TEMPERATURE:
                return cast(float, self._sensor_data["Value"])
            if self.entity_description.key == "UVIndex":
                return cast(int, self._sensor_data["Value"])
        if self.entity_description.key in ("Grass", "Mold", "Ragweed", "Tree", "Ozone"):
            return cast(int, self._sensor_data["Value"])
        if self.entity_description.key == "Ceiling":
            return round(self._sensor_data[self._unit_system]["Value"])
        if self.entity_description.key == "PressureTendency":
            return cast(str, self._sensor_data["LocalizedText"].lower())
        if self.entity_description.device_class == DEVICE_CLASS_TEMPERATURE:
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
