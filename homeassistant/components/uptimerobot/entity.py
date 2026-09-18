"""Base UptimeRobot entity."""

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
    ) -> None:
        """Initialize UptimeRobot entities."""
        super().__init__(coordinator)
        self.entity_description = description
        self._monitor_id = description.key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._monitor_id)},
            name=self._monitor.friendlyName,
            manufacturer="UptimeRobot Team",
            entry_type=DeviceEntryType.SERVICE,
            model=self._monitor.type,
            configuration_url=f"https://uptimerobot.com/dashboard#{self._monitor_id}",
        )
        self._attr_extra_state_attributes = {
            ATTR_TARGET: self._monitor.url,
        }
        self._attr_unique_id = self._monitor_id
        self.api = coordinator.api

    @property
    def _monitor(self) -> UptimeRobotMonitor:
        """Handle monitor updates."""
        return self.coordinator.data[int(self._monitor_id)]
