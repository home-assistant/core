"""Support for the AccuWeather service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONF_NAME,
    DEVICE_CLASS_TEMPERATURE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AccuWeatherDataUpdateCoordinator
from .const import (
    API_IMPERIAL,
    API_METRIC,
    ATTR_ENABLED,
    ATTR_FORECAST,
    ATTR_LABEL,
    ATTR_UNIT_IMPERIAL,
    ATTR_UNIT_METRIC,
    ATTRIBUTION,
    COORDINATOR,
    DOMAIN,
    FORECAST_SENSOR_TYPES,
    MANUFACTURER,
    MAX_FORECAST_DAYS,
    NAME,
    SENSOR_TYPES,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add AccuWeather entities from a config_entry."""
    name: str = entry.data[CONF_NAME]

    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        COORDINATOR
    ]

    sensors: list[AccuWeatherSensor] = []
    for sensor in SENSOR_TYPES:
        sensors.append(AccuWeatherSensor(name, sensor, coordinator))

    if coordinator.forecast:
        for sensor in FORECAST_SENSOR_TYPES:
            for day in range(MAX_FORECAST_DAYS + 1):
                # Some air quality/allergy sensors are only available for certain
                # locations.
                if sensor in coordinator.data[ATTR_FORECAST][0]:
                    sensors.append(
                        AccuWeatherSensor(name, sensor, coordinator, forecast_day=day)
                    )

    async_add_entities(sensors)


class AccuWeatherSensor(CoordinatorEntity, SensorEntity):
    """Define an AccuWeather entity."""

    coordinator: AccuWeatherDataUpdateCoordinator

    def __init__(
        self,
        name: str,
        kind: str,
        coordinator: AccuWeatherDataUpdateCoordinator,
        forecast_day: int | None = None,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        if forecast_day is None:
            self._description = SENSOR_TYPES[kind]
            self._sensor_data: dict[str, Any]
            if kind == "Precipitation":
                self._sensor_data = coordinator.data["PrecipitationSummary"][kind]
            else:
                self._sensor_data = coordinator.data[kind]
        else:
            self._description = FORECAST_SENSOR_TYPES[kind]
            self._sensor_data = coordinator.data[ATTR_FORECAST][forecast_day][kind]
        self._unit_system = API_METRIC if coordinator.is_metric else API_IMPERIAL
        self._name = name
        self.kind = kind
        self._device_class = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self.forecast_day = forecast_day

    @property
    def name(self) -> str:
        """Return the name."""
        if self.forecast_day is not None:
            return f"{self._name} {self._description[ATTR_LABEL]} {self.forecast_day}d"
        return f"{self._name} {self._description[ATTR_LABEL]}"

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        if self.forecast_day is not None:
            return f"{self.coordinator.location_key}-{self.kind}-{self.forecast_day}".lower()
        return f"{self.coordinator.location_key}-{self.kind}".lower()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.coordinator.location_key)},
            "name": NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def state(self) -> StateType:
        """Return the state."""
        if self.forecast_day is not None:
            if self._description["device_class"] == DEVICE_CLASS_TEMPERATURE:
                return cast(float, self._sensor_data["Value"])
            if self.kind == "UVIndex":
                return cast(int, self._sensor_data["Value"])
        if self.kind in ["Grass", "Mold", "Ragweed", "Tree", "Ozone"]:
            return cast(int, self._sensor_data["Value"])
        if self.kind == "Ceiling":
            return round(self._sensor_data[self._unit_system]["Value"])
        if self.kind == "PressureTendency":
            return cast(str, self._sensor_data["LocalizedText"].lower())
        if self._description["device_class"] == DEVICE_CLASS_TEMPERATURE:
            return cast(float, self._sensor_data[self._unit_system]["Value"])
        if self.kind == "Precipitation":
            return cast(float, self._sensor_data[self._unit_system]["Value"])
        if self.kind in ["Wind", "WindGust"]:
            return cast(float, self._sensor_data["Speed"][self._unit_system]["Value"])
        if self.kind in ["WindDay", "WindNight", "WindGustDay", "WindGustNight"]:
            return cast(StateType, self._sensor_data["Speed"]["Value"])
        return cast(StateType, self._sensor_data)

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._description[ATTR_ICON]

    @property
    def device_class(self) -> str | None:
        """Return the device_class."""
        return self._description[ATTR_DEVICE_CLASS]

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        if self.coordinator.is_metric:
            return self._description[ATTR_UNIT_METRIC]
        return self._description[ATTR_UNIT_IMPERIAL]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.forecast_day is not None:
            if self.kind in ["WindDay", "WindNight", "WindGustDay", "WindGustNight"]:
                self._attrs["direction"] = self._sensor_data["Direction"]["English"]
            elif self.kind in ["Grass", "Mold", "Ragweed", "Tree", "UVIndex", "Ozone"]:
                self._attrs["level"] = self._sensor_data["Category"]
            return self._attrs
        if self.kind == "UVIndex":
            self._attrs["level"] = self.coordinator.data["UVIndexText"]
        elif self.kind == "Precipitation":
            self._attrs["type"] = self.coordinator.data["PrecipitationType"]
        return self._attrs

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._description[ATTR_ENABLED]
