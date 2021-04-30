"""Support for the Airly sensor service."""
from __future__ import annotations

from typing import Any, cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AirlyDataUpdateCoordinator
from .const import (
    ATTR_API_PM1,
    ATTR_API_PRESSURE,
    ATTRIBUTION,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
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

    def __init__(
        self, coordinator: AirlyDataUpdateCoordinator, name: str, kind: str
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._name = name
        self._description = SENSOR_TYPES[kind]
        self.kind = kind
        self._state = None
        self._unit_of_measurement = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self) -> str:
        """Return the name."""
        return f"{self._name} {self._description['label']}"

    @property
    def state(self) -> StateType:
        """Return the state."""
        self._state = self.coordinator.data[self.kind]
        if self.kind in [ATTR_API_PM1, ATTR_API_PRESSURE]:
            return round(cast(float, self._state))
        return round(cast(float, self._state), 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str | None:
        """Return the icon."""
        return self._description["icon"]

    @property
    def device_class(self) -> str | None:
        """Return the device_class."""
        return self._description["device_class"]

    @property
    def unique_id(self) -> str:
        """Return a unique_id for this entity."""
        return f"{self.coordinator.latitude}-{self.coordinator.longitude}-{self.kind.lower()}"  # type: ignore[attr-defined]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the device info."""
        return {
            "identifiers": {
                (DOMAIN, self.coordinator.latitude, self.coordinator.longitude)  # type: ignore[attr-defined]
            },
            "name": DEFAULT_NAME,
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self._description["unit"]
