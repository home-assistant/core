"""Support for the Hive devices and services."""

from __future__ import annotations

from typing import Any

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HiveDataUpdateCoordinator


class HiveEntity(CoordinatorEntity[HiveDataUpdateCoordinator]):
    """Initiate Hive Base Class."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HiveDataUpdateCoordinator,
        hive_device: dict[str, Any],
    ) -> None:
        """Initialize the instance."""
        super().__init__(coordinator)
        self.hive = coordinator.hive
        self.device = hive_device
        self._attr_name = self._derive_entity_name(
            hive_device.get("haName"), hive_device.get("device_name")
        )
        self._attr_unique_id = f"{self.device['hiveID']}-{self.device['hiveType']}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device["device_id"])},
            model=self.device["deviceData"]["model"],
            manufacturer=self.device["deviceData"]["manufacturer"],
            name=self.device["device_name"],
            sw_version=self.device["deviceData"]["version"],
            via_device=(DOMAIN, self.device["parentDevice"]),
        )
        self.attributes: dict[str, Any] = {}

    @staticmethod
    def _derive_entity_name(ha_name: str | None, device_name: str | None) -> str | None:
        """Derive the entity name from the Hive device data.

        Because ``_attr_has_entity_name`` is True, Home Assistant prefixes the
        device name automatically. Strip the device-name prefix from ``haName``
        so it is not duplicated, and return ``None`` when the entity represents
        the device itself, when no meaningful suffix remains, or when either
        value is missing from the upstream data.
        """
        if not ha_name or not device_name or ha_name == device_name:
            return None
        if ha_name.startswith(f"{device_name} "):
            suffix = ha_name[len(device_name) + 1 :].strip()
            return suffix or None
        return ha_name

    @property
    def available(self) -> bool:
        """Return True if the coordinator succeeded and the device is online."""
        return super().available and bool(self.device["deviceData"].get("online"))

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update entity state when coordinator data changes."""
        if self.coordinator.data is not None:
            self.device = self.coordinator.data.get(self.device["hiveID"], self.device)
        self._update_state_from_device()
        self.async_write_ha_state()

    def _update_state_from_device(self) -> None:
        """Update entity-specific attributes from self.device.

        Override in subclasses to set ``_attr_*`` fields after each
        coordinator refresh.
        """
