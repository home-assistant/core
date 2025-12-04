"""Provides the base entities."""

from __future__ import annotations

from bleak.exc import BleakError
from togrill_bluetooth.client import Client
from togrill_bluetooth.exceptions import BaseError
from togrill_bluetooth.packets import PacketWrite

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LOGGER, ToGrillCoordinator


class ToGrillEntity(CoordinatorEntity[ToGrillCoordinator]):
    """Coordinator entity for Gardena Bluetooth."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: ToGrillCoordinator, probe_number: int | None = None
    ) -> None:
        """Initialize coordinator entity."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.get_device_info(probe_number)

    def _get_client(self) -> Client:
        client = self.coordinator.client
        if client is None or not client.is_connected:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="disconnected"
            )
        return client

    async def _write_packet(self, packet: PacketWrite) -> None:
        client = self._get_client()
        try:
            await client.write(packet)
        except BleakError as exc:
            LOGGER.debug("Failed to write", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="communication_failed"
            ) from exc
        except BaseError as exc:
            LOGGER.debug("Failed to write", exc_info=True)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="rejected"
            ) from exc
        await self.coordinator.async_request_refresh()
