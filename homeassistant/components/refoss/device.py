"""Entity for Refoss."""

from __future__ import annotations

from refoss_ha.controller.device import BaseDevice
from refoss_ha.enums import Namespace

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class RefossEntity(Entity):
    """RefossDevice."""

    def __init__(self, device: BaseDevice, channel: int) -> None:
        """__init__."""
        self._attr_unique_id = f"refoss.{device.uuid} {channel}"
        self._attr_name = f"{device.dev_name}"
        if channel > 0:
            self._attr_name = f"{device.dev_name}-{channel}"
        self.device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.uuid)},
            manufacturer="refoss",
            model=self.device.device_type,
            name=self.device.dev_name,
            sw_version=self.device.fmware_version,
            hw_version=self.device.hdware_version,
        )

    @property
    def should_poll(self) -> bool:
        """should_poll."""
        return False

    async def async_update(self):
        """async_update."""
        await self.device.async_update()

    async def _async_push_notification_received(
        self, namespace: Namespace, data: dict, uuid: str
    ):
        """_async_push_notification_received."""
        await self.device.async_update_push_state(
            namespace=namespace, data=data, uuid=uuid
        )
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.device.register_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """async_will_remove_from_hass."""
        self.device.unregister_push_notification_handler_coroutine(
            self._async_push_notification_received
        )
