"""Base entity for the Casper Glow integration."""

from __future__ import annotations

from collections.abc import Awaitable

from pycasperglow import CasperGlowError

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac

from .const import DOMAIN
from .coordinator import CasperGlowCoordinator


class CasperGlowEntity(PassiveBluetoothCoordinatorEntity[CasperGlowCoordinator]):
    """Base class for Casper Glow entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CasperGlowCoordinator) -> None:
        """Initialize a Casper Glow entity."""
        super().__init__(coordinator)
        self._device = coordinator.device
        self._attr_device_info = DeviceInfo(
            manufacturer="Casper",
            model="Glow",
            model_id="G01",
            connections={
                (dr.CONNECTION_BLUETOOTH, format_mac(coordinator.device.address))
            },
        )

    async def _async_command(self, coro: Awaitable[None]) -> None:
        """Execute a device command."""
        try:
            await coro
        except CasperGlowError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="communication_error",
                translation_placeholders={"error": str(err)},
            ) from err
