"""Support for the GIOS service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import ATTR_STATE_CLASS, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, ATTR_NAME, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GiosDataUpdateCoordinator
from .const import (
    ATTR_INDEX,
    ATTR_STATION,
    ATTR_UNIT,
    ATTR_VALUE,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a GIOS entities from a config_entry."""
    name = entry.data[CONF_NAME]

    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []

    for sensor in coordinator.data:
        if sensor in SENSOR_TYPES:
            sensors.append(GiosSensor(name, sensor, coordinator))
    async_add_entities(sensors)


class GiosSensor(CoordinatorEntity, SensorEntity):
    """Define an GIOS sensor."""

    coordinator: GiosDataUpdateCoordinator

    def __init__(
        self, name: str, sensor_type: str, coordinator: GiosDataUpdateCoordinator
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._description = SENSOR_TYPES[sensor_type]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(coordinator.gios.station_id))},
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }
        self._attr_icon = "mdi:blur"
        self._attr_name = f"{name} {sensor_type.upper()}"
        self._attr_state_class = self._description.get(ATTR_STATE_CLASS)
        self._attr_unique_id = f"{coordinator.gios.station_id}-{sensor_type}"
        self._attr_unit_of_measurement = self._description.get(ATTR_UNIT)
        self._sensor_type = sensor_type
        self._state = None
        self._attrs: dict[str, Any] = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_STATION: self.coordinator.gios.station_name,
        }

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data[self._sensor_type].get(ATTR_INDEX):
            self._attrs[ATTR_NAME] = self.coordinator.data[self._sensor_type][ATTR_NAME]
            self._attrs[ATTR_INDEX] = self.coordinator.data[self._sensor_type][
                ATTR_INDEX
            ]
        return self._attrs

    @property
    def state(self) -> StateType:
        """Return the state."""
        self._state = self.coordinator.data[self._sensor_type][ATTR_VALUE]
        if self._description.get(ATTR_VALUE):
            return cast(StateType, self._description[ATTR_VALUE](self._state))
        return cast(StateType, self._state)
