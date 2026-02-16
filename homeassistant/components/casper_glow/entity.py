"""Base entity for the Casper Glow integration."""

from __future__ import annotations

from collections.abc import Awaitable
import logging

from pycasperglow import CasperGlowError

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .coordinator import CasperGlowCoordinator

_LOGGER = logging.getLogger(__name__)


class CasperGlowEntity(PassiveBluetoothCoordinatorEntity[CasperGlowCoordinator]):
    """Base class for Casper Glow entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize a Casper Glow entity."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = DeviceInfo(
            name=coordinator.title,
            manufacturer="Casper",
            model="Glow",
            connections={(dr.CONNECTION_BLUETOOTH, coordinator.device.address)},
        )

    async def _async_command(self, coro: Awaitable[None]) -> None:
        """Execute a device command, handling errors and availability logging."""
        try:
            await coro
        except CasperGlowError as err:
            if not self.coordinator.command_unavailable_logged:
                _LOGGER.info("Device is unavailable")
                self.coordinator.command_unavailable_logged = True
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
        if self.coordinator.command_unavailable_logged:
            _LOGGER.info("Device is back online")
            self.coordinator.command_unavailable_logged = False

    def _log_back_online_if_needed(self) -> None:
        """Log recovery and clear the unavailability flag if previously set."""
        if self.coordinator.command_unavailable_logged:
            _LOGGER.info("Device is back online")
            self.coordinator.command_unavailable_logged = False
