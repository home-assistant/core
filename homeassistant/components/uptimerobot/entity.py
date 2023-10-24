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
            identifiers={(DOMAIN, str(self.monitor.id))},
            name=self.monitor.friendly_name,
            manufacturer="UptimeRobot Team",
            entry_type=DeviceEntryType.SERVICE,
            model=self.monitor.type.name,
            configuration_url=f"https://uptimerobot.com/dashboard#{self.monitor.id}",
        )
        self._attr_extra_state_attributes = {
            ATTR_TARGET: self.monitor.url,
        }
        self._attr_unique_id = str(self.monitor.id)
        self.api = coordinator.api

    @property
    def _monitors(self) -> list[UptimeRobotMonitor]:
        """Return all monitors."""
        return self.coordinator.data or []

    @property
    def monitor(self) -> UptimeRobotMonitor:
        """Return the monitor for this entity."""
        return next(
            (
                monitor
                for monitor in self._monitors
                if str(monitor.id) == self.entity_description.key
            ),
            self._monitor,
        )

    @property
    def monitor_available(self) -> bool:
        """Returtn if the monitor is available."""
        return bool(self.monitor.status == 2)
