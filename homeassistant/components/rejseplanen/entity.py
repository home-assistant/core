"""Updater status sensor for Rejseplanen integration."""

from typing import Any

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class RejseplanenUpdaterStatusSensor(CoordinatorEntity):
    """Sensor to show the status of the Rejseplanen updater."""

    _attr_has_entity_name = True
    _attr_name = "Updater Status"
    _attr_icon = "mdi:cloud-check"

    def __init__(self, coordinator, entry_id) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_updater_status"

    @property
    def available(self) -> bool:
        """Return True if the coordinator is available."""
        return self.coordinator.last_update_success

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if self.coordinator.last_update_success:
            return "Online"
        return "Offline"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            "last_update": self.coordinator.last_update_success,
            "last_update_time": getattr(self.coordinator, "last_update_success_time", None),
            "update_interval": (
                self.coordinator.update_interval.total_seconds()
                if self.coordinator.update_interval
                else None
            ),
        }
