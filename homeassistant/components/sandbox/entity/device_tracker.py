"""Sandbox proxy for device_tracker entities."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import ScannerEntity, TrackerEntity

from . import SandboxEntityDescription, SandboxEntityManager, SandboxProxyEntity


class SandboxTrackerEntity(SandboxProxyEntity, TrackerEntity):
    """Proxy for a GPS device tracker entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy tracker entity."""
        super().__init__(description, manager)
        if source_type := description.capabilities.get("source_type"):
            self._attr_source_type = SourceType(source_type)

    @property
    def latitude(self) -> float | None:
        """Return the latitude."""
        return self._state_cache.get("latitude")

    @property
    def longitude(self) -> float | None:
        """Return the longitude."""
        return self._state_cache.get("longitude")

    @property
    def location_accuracy(self) -> float:
        """Return the location accuracy."""
        return self._state_cache.get("location_accuracy", 0)

    @property
    def location_name(self) -> str | None:
        """Return the location name."""
        return self._state_cache.get("location_name")

    @property
    def battery_level(self) -> int | None:
        """Return the battery level."""
        return self._state_cache.get("battery_level")


class SandboxScannerEntity(SandboxProxyEntity, ScannerEntity):
    """Proxy for a scanner device tracker entity in a sandbox."""

    def __init__(
        self,
        description: SandboxEntityDescription,
        manager: SandboxEntityManager,
    ) -> None:
        """Initialize the proxy scanner entity."""
        super().__init__(description, manager)
        if source_type := description.capabilities.get("source_type"):
            self._attr_source_type = SourceType(source_type)

    @property
    def is_connected(self) -> bool:
        """Return if the device is connected."""
        state = self._state_cache.get("state")
        return state == "home"

    @property
    def ip_address(self) -> str | None:
        """Return the IP address."""
        return self._state_cache.get("ip_address")

    @property
    def mac_address(self) -> str | None:
        """Return the MAC address."""
        return self._state_cache.get("mac_address")

    @property
    def hostname(self) -> str | None:
        """Return the hostname."""
        return self._state_cache.get("hostname")
