"""Support for the Airly sensor service."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONF_NAME,
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PM1,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    PRESSURE_HPA,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirlyDataUpdateCoordinator
from .const import (
    ATTR_ADVICE,
    ATTR_API_ADVICE,
    ATTR_API_CAQI,
    ATTR_API_CAQI_DESCRIPTION,
    ATTR_API_CAQI_LEVEL,
    ATTR_API_HUMIDITY,
    ATTR_API_PM1,
    ATTR_API_PM10,
    ATTR_API_PM25,
    ATTR_API_PRESSURE,
    ATTR_API_TEMPERATURE,
    ATTR_DESCRIPTION,
    ATTR_LEVEL,
    ATTR_LIMIT,
    ATTR_PERCENT,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SUFFIX_LIMIT,
    SUFFIX_PERCENT,
    URL,
)

PARALLEL_UPDATES = 1


@dataclass
class AirlySensorEntityDescription(SensorEntityDescription):
    """Class describing Airly sensor entities."""

    value: Callable = round


SENSOR_TYPES: tuple[AirlySensorEntityDescription, ...] = (
    AirlySensorEntityDescription(
        key=ATTR_API_CAQI,
        device_class=DEVICE_CLASS_AQI,
        name=ATTR_API_CAQI,
        native_unit_of_measurement="CAQI",
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM1,
        device_class=DEVICE_CLASS_PM1,
        name=ATTR_API_PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM25,
        device_class=DEVICE_CLASS_PM25,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PM10,
        device_class=DEVICE_CLASS_PM10,
        name=ATTR_API_PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_HUMIDITY,
        device_class=DEVICE_CLASS_HUMIDITY,
        name=ATTR_API_HUMIDITY.capitalize(),
        native_unit_of_measurement=PERCENTAGE,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_PRESSURE,
        device_class=DEVICE_CLASS_PRESSURE,
        name=ATTR_API_PRESSURE.capitalize(),
        native_unit_of_measurement=PRESSURE_HPA,
        state_class=STATE_CLASS_MEASUREMENT,
    ),
    AirlySensorEntityDescription(
        key=ATTR_API_TEMPERATURE,
        device_class=DEVICE_CLASS_TEMPERATURE,
        name=ATTR_API_TEMPERATURE.capitalize(),
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=STATE_CLASS_MEASUREMENT,
        value=lambda value: round(value, 1),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Airly sensor entities based on a config entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for description in SENSOR_TYPES:
        # When we use the nearest method, we are not sure which sensors are available
        if coordinator.data.get(description.key):
            sensors.append(AirlySensor(coordinator, name, description))

    async_add_entities(sensors, False)


class AirlySensor(CoordinatorEntity, SensorEntity):
    """Define an Airly sensor."""

    coordinator: AirlyDataUpdateCoordinator
    entity_description: AirlySensorEntityDescription

    def __init__(
        self,
        coordinator: AirlyDataUpdateCoordinator,
        name: str,
        description: AirlySensorEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"{coordinator.latitude}-{coordinator.longitude}")},
            manufacturer=MANUFACTURER,
            name=DEFAULT_NAME,
            configuration_url=URL.format(
                latitude=coordinator.latitude, longitude=coordinator.longitude
            ),
        )
        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = (
            f"{coordinator.latitude}-{coordinator.longitude}-{description.key}".lower()
        )
        self._attrs: dict[str, Any] = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state."""
        state = self.coordinator.data[self.entity_description.key]
        return cast(StateType, self.entity_description.value(state))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.entity_description.key == ATTR_API_CAQI:
            self._attrs[ATTR_LEVEL] = self.coordinator.data[ATTR_API_CAQI_LEVEL]
            self._attrs[ATTR_ADVICE] = self.coordinator.data[ATTR_API_ADVICE]
            self._attrs[ATTR_DESCRIPTION] = self.coordinator.data[
                ATTR_API_CAQI_DESCRIPTION
            ]
        if self.entity_description.key == ATTR_API_PM25:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM25}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM25}_{SUFFIX_PERCENT}"]
            )
        if self.entity_description.key == ATTR_API_PM10:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM10}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM10}_{SUFFIX_PERCENT}"]
            )
        return self._attrs
