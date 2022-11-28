"""Support for iss binary sensor."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import IssData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_ISS_NEXT_RISE = "next_rise"
ATTR_ISS_NUMBER_PEOPLE_SPACE = "number_of_people_in_space"

DEFAULT_NAME = "ISS"
DEFAULT_DEVICE_CLASS = "visible"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator: DataUpdateCoordinator[IssData] = hass.data[DOMAIN]

    name = entry.title
    show_on_map = entry.options.get(CONF_SHOW_ON_MAP, False)

    async_add_entities([IssBinarySensor(coordinator, name, show_on_map)])


class IssBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[IssData]], BinarySensorEntity
):
    """Implementation of the ISS binary sensor."""

    _attr_device_class = DEFAULT_DEVICE_CLASS

    def __init__(
        self, coordinator: DataUpdateCoordinator[IssData], name: str, show: bool
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._state = None
        self._attr_name = name
        self._show_on_map = show

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data.is_above is True

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        attrs = {
            ATTR_ISS_NUMBER_PEOPLE_SPACE: self.coordinator.data.number_of_people_in_space,
            ATTR_ISS_NEXT_RISE: self.coordinator.data.next_rise,
        }
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
