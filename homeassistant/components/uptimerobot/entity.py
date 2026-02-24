"""Base UptimeRobot entity."""

from __future__ import annotations

from pyuptimerobot import UptimeRobotMonitor

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UptimeRobotDataUpdateCoordinator
from .const import ATTR_TARGET, ATTRIBUTION, DOMAIN


class UptimeRobotEntity(CoordinatorEntity[UptimeRobotDataUpdateCoordinator]):
    """Base UptimeRobot entity."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: UptimeRobotDataUpdateCoordinator,
        description: EntityDescription,
        monitor: UptimeRobotMonitor,
    ) -> None:
        """Initialize UptimeRobot entities."""
        super().__init__(coordinator)
        self.entity_description = description
        self._monitor_id = str(monitor.id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._monitor_id)},
            name=self.monitor.friendlyName,
            manufacturer="UptimeRobot Team",
            entry_type=DeviceEntryType.SERVICE,
            model=self.monitor.type,
            configuration_url=f"https://uptimerobot.com/dashboard#{self.monitor.id}",
        )
        self._attr_extra_state_attributes = {
            ATTR_TARGET: self.monitor.url,
        }
        self._attr_unique_id = self._monitor_id
        self.api = coordinator.api

    @property
    def available(self) -> bool:
        """Return if the entity is available."""
        return super().available and self._monitor_id in self.coordinator.data

    @property
    def monitor(self) -> UptimeRobotMonitor:
        """Return the monitor for this entity."""
        return self.coordinator.data[self._monitor_id]
