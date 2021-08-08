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
        return str(self.monitor.id) if self.monitor else None

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this AdGuard Home instance."""
        if self.monitor:
            return {
                "identifiers": {(DOMAIN, str(self.monitor.id))},
                "name": "Uptime Robot",
                "manufacturer": "Uptime Robot Team",
                "entry_type": "service",
                "model": self.monitor.type.name,
            }
        return {}

    @property
    def monitors(self) -> list[UptimeRobotMonitor]:
        """Return all monitors."""
        return self.coordinator.data or []

    @property
    def monitor(self) -> UptimeRobotMonitor | None:
        """Return the monitor for this entity."""
        return next(
            (
                monitor
                for monitor in self.monitors
                if str(monitor.id) == self.entity_description.key
            ),
            None,
        )

    @property
    def monitor_available(self) -> bool:
        """Returtn if the monitor is available."""
        status: bool = self.monitor.status == 2 if self.monitor else False
        return status

    @property
    def available(self) -> bool:
        """Returtn if entity is available."""
        if not self.coordinator.last_update_success:
            return False
        return self.monitor is not None
