"""Base entity for Lyngdorf integration."""

from typing import override

from lyngdorf import LyngdorfReceiver

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity


class LyngdorfEntity(Entity):
    """Base Lyngdorf entity."""

    _attr_has_entity_name = True
    _attr_available = True
    _attr_should_poll = False

    def __init__(self, receiver: LyngdorfReceiver, device_info: DeviceInfo) -> None:
        """Initialize the entity."""
        self._receiver = receiver
        self._attr_device_info = device_info

    @override
    async def async_added_to_hass(self) -> None:
        """Register notification callback when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._receiver.on_change(self._handle_receiver_update))
        self._update_availability()

    @callback
    def _handle_receiver_update(self) -> None:
        """Handle receiver updates."""
        self._update_availability()
        self.async_write_ha_state()

    @callback
    def _update_availability(self) -> None:
        """Update availability from receiver connection status."""
        self._attr_available = self._receiver.connected
