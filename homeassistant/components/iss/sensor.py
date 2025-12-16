"""Support for iss sensor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_SHOW_ON_MAP
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator.people import IssPeopleCoordinator
from .coordinator.position import IssPositionCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]

    position_coordinator = data["position_coordinator"]
    people_coordinator = data["people_coordinator"]

    show_on_map = entry.options.get(CONF_SHOW_ON_MAP, False)

    async_add_entities(
        [
            IssPositionSensor(
                position_coordinator=position_coordinator,
                entry=entry,
                show=show_on_map,
            ),
            IssPeopleSensor(
                people_coordinator=people_coordinator,
                entry=entry,
            ),
        ]
    )


class IssPositionSensor(CoordinatorEntity[IssPositionCoordinator], SensorEntity):
    """Implementation of the ISS position sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "location"

    def __init__(
        self,
        *,
        position_coordinator: IssPositionCoordinator,
        entry: ConfigEntry,
        show: bool,
    ) -> None:
        """Initialize the position sensor."""
        super().__init__(position_coordinator)

        self._attr_unique_id = f"{entry.entry_id}_location"
        self._show_on_map = show
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

        self._attr_icon = "mdi:space-station"

    @property
    def native_value(self) -> str | None:
        """Coordinates of the station."""
        position_data: dict[str, str] | None = self.coordinator.data
        if not position_data:
            return None

        longitude_short = round(float(position_data.get("longitude", "0.0")), 3)
        latitude_short = round(float(position_data.get("latitude", "0.0")), 3)
        return f"Latitude:  {latitude_short}°\nLongitude: {longitude_short}°"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        position_data: dict[str, str] | None = self.coordinator.data
        if not position_data:
            return {}

        attrs: dict[str, Any] = {}

        longitude_short = round(float(position_data.get("longitude", "0.0")), 2)
        latitude_short = round(float(position_data.get("latitude", "0.0")), 2)

        if self._show_on_map:
            attrs[ATTR_LONGITUDE] = longitude_short
            attrs[ATTR_LATITUDE] = latitude_short
            attrs["entity_picture"] = "https://brands.home-assistant.io/iss/icon@2x.png"
            attrs["friendly_name"] = "ISS"
        else:
            attrs["long"] = position_data.get("longitude")
            attrs["lat"] = position_data.get("latitude")

        attrs["last_updated"] = self.coordinator.last_update_success
        return attrs


class IssPeopleSensor(CoordinatorEntity[IssPeopleCoordinator], SensorEntity):
    """Implementation of the ISS people on board sensor."""

    _attr_has_entity_name = True
    _attr_translation_key = "people_on_board"
    _attr_icon = "mdi:account-multiple"
    _attr_native_unit_of_measurement = "people"

    def __init__(
        self,
        *,
        people_coordinator: IssPeopleCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the people sensor."""
        super().__init__(people_coordinator)

        self._attr_unique_id = f"{entry.entry_id}_people"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=DEFAULT_NAME,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> int | None:
        """Return the number of people in space."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get("number")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        people_list = self.coordinator.data.get("people", [])
        return {
            "people": [person.get("name") for person in people_list],
        }
