"""Base entity for the EARN-E P1 Meter integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EarnEP1Coordinator


class EarnEP1Entity(CoordinatorEntity[EarnEP1Coordinator]):
    """Base class for EARN-E P1 entities."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.serial or self.coordinator.host)},
            name="EARN-E P1 Meter",
            manufacturer="EARN-E",
            model=self.coordinator.model,
            sw_version=self.coordinator.sw_version,
        )
