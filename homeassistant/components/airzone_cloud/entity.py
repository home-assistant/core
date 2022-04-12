"""Entity classes for the Airzone Cloud integration."""
from __future__ import annotations

from typing import Any

from aioairzone_cloud.const import AZD_ID, AZD_NAME, AZD_SYSTEM, AZD_ZONES

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator


class AirzoneEntity(CoordinatorEntity[AirzoneUpdateCoordinator]):
    """Define an Airzone entity."""

    def get_airzone_value(self, key: str) -> Any:
        """Return Airzone entity value by key."""
        raise NotImplementedError()


class AirzoneZoneEntity(AirzoneEntity):
    """Define an Airzone Zone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        entry: ConfigEntry,
        system_zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.system_id = zone_data[AZD_SYSTEM]
        self.system_zone_id = system_zone_id
        self.zone_id = zone_data[AZD_ID]

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_{system_zone_id}")},
            manufacturer=MANUFACTURER,
            name=zone_data[AZD_NAME],
            via_device=(DOMAIN, f"{entry.entry_id}_{self.system_id}"),
        )
        self._attr_unique_id = entry.unique_id or entry.entry_id

    def get_airzone_value(self, key: str) -> Any:
        """Return zone value by key."""
        value = None
        if zone := self.coordinator.data[AZD_ZONES].get(self.system_zone_id):
            if key in zone:
                value = zone[key]
        return value
