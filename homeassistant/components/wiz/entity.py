"""WiZ integration entities."""
from __future__ import annotations

from typing import Any

from pywizlight.bulblibrary import BulbType

from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.entity import DeviceInfo, ToggleEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .models import WizData


class WizToggleEntity(CoordinatorEntity, ToggleEntity):
    """Representation of WiZ toggle entity."""

    def __init__(self, wiz_data: WizData, name: str) -> None:
        """Initialize an WiZ device."""
        super().__init__(wiz_data.coordinator)
        self._device = wiz_data.bulb
        bulb_type: BulbType = self._device.bulbtype
        self._attr_unique_id = self._device.mac
        self._attr_name = name
        hw_data = bulb_type.name.split("_")
        board = hw_data.pop(0)
        model = hw_data.pop(0)
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._device.mac)},
            name=name,
            manufacturer="WiZ",
            model=model,
            hw_version=f"{board} {hw_data[0]}" if hw_data else board,
            sw_version=bulb_type.fw_version,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._async_update_attrs()
        super()._handle_coordinator_update()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_on = self._device.status

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Instruct the device to turn off."""
        await self._device.turn_off()
        await self.coordinator.async_request_refresh()
