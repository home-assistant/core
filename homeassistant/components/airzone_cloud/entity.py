"""Entity classes for the Airzone Cloud integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from aioairzone_cloud.const import (
    AZD_AIDOOS,
    AZD_AVAILABLE,
    AZD_FIRMWARE,
    AZD_NAME,
    AZD_SYSTEM_ID,
    AZD_WEBSERVER,
    AZD_WEBSERVERS,
    AZD_ZONES,
)

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import AirzoneUpdateCoordinator


class AirzoneEntity(CoordinatorEntity[AirzoneUpdateCoordinator], ABC):
    """Define an Airzone Cloud entity."""

    @property
    def available(self) -> bool:
        """Return Airzone Cloud entity availability."""
        return super().available and self.get_airzone_value(AZD_AVAILABLE)

    @abstractmethod
    def get_airzone_value(self, key: str) -> Any:
        """Return Airzone Cloud entity value by key."""


class AirzoneAidooEntity(AirzoneEntity):
    """Define an Airzone Cloud Aidoo entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        aidoo_id: str,
        aidoo_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.aidoo_id = aidoo_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, aidoo_id)},
            manufacturer=MANUFACTURER,
            name=aidoo_data[AZD_NAME],
            via_device=(DOMAIN, aidoo_data[AZD_WEBSERVER]),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return Aidoo value by key."""
        value = None
        if aidoo := self.coordinator.data[AZD_AIDOOS].get(self.aidoo_id):
            value = aidoo.get(key)
        return value


class AirzoneWebServerEntity(AirzoneEntity):
    """Define an Airzone Cloud WebServer entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        ws_id: str,
        ws_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.ws_id = ws_id

        self._attr_device_info = DeviceInfo(
            connections={(dr.CONNECTION_NETWORK_MAC, ws_id)},
            identifiers={(DOMAIN, ws_id)},
            manufacturer=MANUFACTURER,
            name=ws_data[AZD_NAME],
            sw_version=ws_data[AZD_FIRMWARE],
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return WebServer value by key."""
        value = None
        if webserver := self.coordinator.data[AZD_WEBSERVERS].get(self.ws_id):
            value = webserver.get(key)
        return value


class AirzoneZoneEntity(AirzoneEntity):
    """Define an Airzone Cloud Zone entity."""

    def __init__(
        self,
        coordinator: AirzoneUpdateCoordinator,
        zone_id: str,
        zone_data: dict[str, Any],
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)

        self.system_id = zone_data[AZD_SYSTEM_ID]
        self.zone_id = zone_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, zone_id)},
            manufacturer=MANUFACTURER,
            name=zone_data[AZD_NAME],
            via_device=(DOMAIN, self.system_id),
        )

    def get_airzone_value(self, key: str) -> Any:
        """Return zone value by key."""
        value = None
        if zone := self.coordinator.data[AZD_ZONES].get(self.zone_id):
            value = zone.get(key)
        return value
