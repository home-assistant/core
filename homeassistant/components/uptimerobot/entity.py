"""Base UptimeRobot entity."""
from __future__ import annotations

from pyuptimerobot import UptimeRobotMonitor

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import DeviceInfo, EntityDescription
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import ATTR_TARGET, ATTRIBUTION, DOMAIN


class UptimeRobotEntity(CoordinatorEntity):
    """Base UptimeRobot entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        description: EntityDescription,
        target: str,
    ) -> None:
        """Initialize Uptime Robot entities."""
        super().__init__(coordinator)
        self.entity_description = description
        self._target = target
        self._attr_extra_state_attributes = {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            ATTR_TARGET: self._target,
        }

    @property
    def unique_id(self) -> str | None:
        """Return the unique_id of the entity."""
        return str(self.monitor.id)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AdGuard Home instance."""
        return {
            "identifiers": {(DOMAIN, str(self.monitor.id))},
            "name": "Uptime Robot",
            "manufacturer": "Uptime Robot Team",
            "entry_type": "service",
            "model": self.monitor.type.name,
        }

    @property
    def monitors(self) -> list[UptimeRobotMonitor]:
        """Return all monitors."""
        return self.coordinator.data or []

    @property
    def monitor(self) -> UptimeRobotMonitor:
        """Return the monitor for this entity."""
        return next(
            monitor
            for monitor in self.monitors
            if str(monitor.id) == self.entity_description.key
        )

    @property
    def monitor_available(self) -> bool:
        """Returtn if the monitor is available."""
        return bool(self.monitor.status == 2)
