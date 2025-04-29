"""Entity classes for Airzone MQTT integration."""

from __future__ import annotations

import logging
from typing import Any

from airzone_mqtt.const import (
    AZD_DEVICE_ID,
    AZD_IS_CONNECTED,
    AZD_NAME,
    AZD_SYSTEM_ID,
    AZD_ZONES,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class AirzoneEntity(CoordinatorEntity[AirzoneUpdateCoordinator]):
    """Define an Airzone entity."""

    _attr_has_entity_name = True

    def get_airzone_value(self, key: str) -> Any:
        """Return Airzone entity value by key."""
        raise NotImplementedError


class AirzoneZoneEntity(AirzoneEntity):
    """Define an Airzone Zone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        airzone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.airzone_id = airzone_id
        self.device_id = zone_data[AZD_DEVICE_ID]
        self.system_id = zone_data[AZD_SYSTEM_ID]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{airzone_id}")},
            manufacturer=MANUFACTURER,
            name=zone_data[AZD_NAME],
        )
        self._attr_unique_id = entry.entry_id

    @property
    def available(self) -> bool:
        """Return zone availability."""
        return super().available and self.get_airzone_value(AZD_IS_CONNECTED)

    def get_airzone_value(self, key: str) -> Any:
        """Return zone value by key."""
        value = None
        if zone := self.coordinator.data[AZD_ZONES].get(self.airzone_id):
            if key in zone:
                value = zone[key]
        return value
