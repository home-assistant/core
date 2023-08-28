"""Support for iss sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import IssData
from .const import DEFAULT_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator[IssData] = hass.data[DOMAIN]

    show_on_map = entry.options.get(CONF_SHOW_ON_MAP, False)

    async_add_entities([IssSensor(coordinator, entry, show_on_map)])


class IssSensor(CoordinatorEntity[DataUpdateCoordinator[IssData]], SensorEntity):
    """Implementation of the ISS sensor."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IssData],
        entry: ConfigEntry,
        show: bool,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_people"
        self._show_on_map = show
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int:
        """Return number of people in space."""
        return self.coordinator.data.number_of_people_in_space

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = {}
        if self._show_on_map:
            attrs[ATTR_LONGITUDE] = self.coordinator.data.current_location.get(
                "longitude"
            )
            attrs[ATTR_LATITUDE] = self.coordinator.data.current_location.get(
                "latitude"
            )
        else:
            attrs["long"] = self.coordinator.data.current_location.get("longitude")
            attrs["lat"] = self.coordinator.data.current_location.get("latitude")

        return attrs
