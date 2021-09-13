"""Support for getting statistical data from a Pi-hole system."""
from __future__ import annotations

from typing import Any

from hole import Hole

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import PiHoleEntity
from .const import (
    ATTR_BLOCKED_DOMAINS,
    ATTR_CORE_CURRENT,
    ATTR_CORE_LATEST,
    ATTR_WEB_CURRENT,
    ATTR_WEB_LATEST,
    ATTR_FTL_CURRENT,
    ATTR_FTL_LATEST,
    DATA_KEY_API,
    DATA_KEY_API_VERSIONS,
    DATA_KEY_COORDINATOR,
    DOMAIN as PIHOLE_DOMAIN,
    SENSOR_TYPES,
    PiHoleSensorEntityDescription,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Pi-hole sensor."""
    name = entry.data[CONF_NAME]
    hole_data = hass.data[PIHOLE_DOMAIN][entry.entry_id]
    sensors = [
        PiHoleSensor(
            hole_data[DATA_KEY_API],
            hole_data[DATA_KEY_API_VERSIONS],
            hole_data[DATA_KEY_COORDINATOR],
            name,
            entry.entry_id,
            description,
        )
        for description in SENSOR_TYPES
    ]
    async_add_entities(sensors, True)


class PiHoleSensor(PiHoleEntity, SensorEntity):
    """Representation of a Pi-hole sensor."""

    entity_description: PiHoleSensorEntityDescription

    def __init__(
        self,
        api: Hole,
        api_versions: Hole,
        coordinator: DataUpdateCoordinator,
        name: str,
        server_unique_id: str,
        description: PiHoleSensorEntityDescription,
    ) -> None:
        """Initialize a Pi-hole sensor."""
        super().__init__(api, coordinator, name, server_unique_id)
        self.entity_description = description

        self._attr_name = f"{name} {description.name}"
        self._attr_unique_id = f"{self._server_unique_id}/{description.name}"

    @property
    def native_value(self) -> Any:
        """Return the state of the device."""
        if self.entity_description.key == "available_updates":
            available_updates = 0
            if self.api_versions.data["core_update"]:
                available_updates += 1
            if self.api_versions.data["web_update"]:
                available_updates += 1
            if self.api_versions.data["FTL_update"]:
                available_updates += 1
            return available_updates
        else:
            try:
                return round(self.api.data[self.entity_description.key], 2)
            except TypeError:
                return self.api.data[self.entity_description.key]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the Pi-hole."""
        if self.entity_description.key == "available_updates":
            return {
                ATTR_CORE_CURRENT: self.api_versions.data[ATTR_CORE_CURRENT],
                ATTR_CORE_LATEST: self.api_versions.data[ATTR_CORE_LATEST],
                ATTR_WEB_CURRENT: self.api_versions.data[ATTR_WEB_CURRENT],
                ATTR_WEB_LATEST: self.api_versions.data[ATTR_WEB_LATEST],
                ATTR_FTL_CURRENT: self.api_versions.data[ATTR_FTL_CURRENT],
                ATTR_FTL_LATEST: self.api_versions.data[ATTR_FTL_LATEST]
            }
        else:
            return {ATTR_BLOCKED_DOMAINS: self.api.data["domains_being_blocked"]}
