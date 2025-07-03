"""Provides the HusqvarnaAutomowerBleEntity."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import HusqvarnaCoordinator

KEEP_ALIVE_INTERVAL = timedelta(seconds=15)


class HusqvarnaAutomowerBleEntity(CoordinatorEntity[HusqvarnaCoordinator]):
    """HusqvarnaCoordinator entity for Husqvarna Automower Bluetooth."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HusqvarnaCoordinator) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.address}_{coordinator.channel_id}")},
            manufacturer=MANUFACTURER,
            model_id=coordinator.model,
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity addition to Home Assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass,
                self.coordinator.async_keep_alive,
                interval=KEEP_ALIVE_INTERVAL,
            )
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.mower.is_connected()
