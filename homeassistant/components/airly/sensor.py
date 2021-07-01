"""Support for the Airly sensor service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_DEVICE_CLASS,
    ATTR_ICON,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
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
    ATTR_API_PM10,
    ATTR_API_PM25,
    ATTR_DESCRIPTION,
    ATTR_LABEL,
    ATTR_LEVEL,
    ATTR_LIMIT,
    ATTR_PERCENT,
    ATTR_UNIT,
    ATTR_VALUE,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
    SUFFIX_LIMIT,
    SUFFIX_PERCENT,
)

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Airly sensor entities based on a config entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    for sensor in SENSOR_TYPES:
        # When we use the nearest method, we are not sure which sensors are available
        if coordinator.data.get(sensor):
            sensors.append(AirlySensor(coordinator, name, sensor))

    async_add_entities(sensors, False)


class AirlySensor(CoordinatorEntity, SensorEntity):
    """Define an Airly sensor."""

    coordinator: AirlyDataUpdateCoordinator

    def __init__(
        self, coordinator: AirlyDataUpdateCoordinator, name: str, kind: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._description = description = SENSOR_TYPES[kind]
        self._attr_device_class = description.get(ATTR_DEVICE_CLASS)
        self._attr_icon = description.get(ATTR_ICON)
        self._attr_name = f"{name} {description[ATTR_LABEL]}"
        self._attr_state_class = description.get(ATTR_STATE_CLASS)
        self._attr_unique_id = (
            f"{coordinator.latitude}-{coordinator.longitude}-{kind.lower()}"
        )
        self._attr_unit_of_measurement = description.get(ATTR_UNIT)
        self._attrs: dict[str, Any] = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self.kind = kind

    @property
    def state(self) -> StateType:
        """Return the state."""
        state = self.coordinator.data[self.kind]
        return cast(StateType, self._description[ATTR_VALUE](state))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.kind == ATTR_API_CAQI:
            self._attrs[ATTR_LEVEL] = self.coordinator.data[ATTR_API_CAQI_LEVEL]
            self._attrs[ATTR_ADVICE] = self.coordinator.data[ATTR_API_ADVICE]
            self._attrs[ATTR_DESCRIPTION] = self.coordinator.data[
                ATTR_API_CAQI_DESCRIPTION
            ]
        if self.kind == ATTR_API_PM25:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM25}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM25}_{SUFFIX_PERCENT}"]
            )
        if self.kind == ATTR_API_PM10:
            self._attrs[ATTR_LIMIT] = self.coordinator.data[
                f"{ATTR_API_PM10}_{SUFFIX_LIMIT}"
            ]
            self._attrs[ATTR_PERCENT] = round(
                self.coordinator.data[f"{ATTR_API_PM10}_{SUFFIX_PERCENT}"]
            )
        return self._attrs

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {
                (
                    DOMAIN,
                    f"{self.coordinator.latitude}-{self.coordinator.longitude}",
                )
            },
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }
