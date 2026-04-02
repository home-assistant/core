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
        self._monitor = monitor
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(self._monitor.id))},
            name=self._monitor.friendlyName,
            manufacturer="UptimeRobot Team",
            entry_type=DeviceEntryType.SERVICE,
            model=self._monitor.type,
            configuration_url=f"https://uptimerobot.com/dashboard#{self._monitor.id}",
        )
        self._attr_extra_state_attributes = {
            ATTR_TARGET: self._monitor.url,
        }
        self._attr_unique_id = str(self._monitor.id)
        self.api = coordinator.api
