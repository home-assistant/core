"""Tuya Home Assistant Base Device Model."""

from __future__ import annotations

from typing import Any

from tuya_sharing import CustomerDevice, Manager

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, LOGGER, TUYA_HA_SIGNAL_UPDATE_ENTITY
from .models import DeviceWrapper


class TuyaEntity(Entity):
    """Tuya base device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: CustomerDevice, device_manager: Manager) -> None:
        """Init TuyaHaEntity."""
        self._attr_unique_id = f"tuya.{device.id}"
        # TuyaEntity initialize mq can subscribe
        device.set_up = True
        self.device = device
        self.device_manager = device_manager

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="Tuya",
            name=self.device.name,
            model=self.device.product_name,
            model_id=self.device.product_id,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device.online

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{TUYA_HA_SIGNAL_UPDATE_ENTITY}_{self.device.id}",
                self._handle_state_update,
            )
        )

    async def _handle_state_update(
        self,
        updated_status_properties: list[str] | None,
        dp_timestamps: dict[str, int] | None,
    ) -> None:
        """Called when Tuya device sends an update."""
        if (
            # If updated_status_properties is None, we should not skip,
            # as we don't have information on what was updated
            # This happens for example on online/offline updates, where
            # we still want to update the entity state but we have nothing
            # to process
            updated_status_properties is None
            # If we have data to process, we check if we should skip the
            # state_write based on the dpcode wrapper logic
            or await self._process_device_update(
                updated_status_properties, dp_timestamps
            )
        ):
            self.async_write_ha_state()

    async def _process_device_update(
        self,
        updated_status_properties: list[str],
        dp_timestamps: dict[str, int] | None,
    ) -> bool:
        """Called when Tuya device sends an update with updated properties.

        Returns True if the Home Assistant state should be written,
        or False if the state write should be skipped.
        """
        return True

    async def _async_send_commands(self, commands: list[dict[str, Any]]) -> None:
        """Send a list of commands to the device."""
        LOGGER.debug("Sending commands for device %s: %s", self.device.id, commands)
        if not commands:
            return
        await self.hass.async_add_executor_job(
            self.device_manager.send_commands, self.device.id, commands
        )

    def _read_wrapper[T](self, wrapper: DeviceWrapper[T] | None) -> T | None:
        """Read the wrapper device status."""
        if wrapper is None:
            return None
        return wrapper.read_device_status(self.device)

    async def _async_send_wrapper_updates[T](
        self, wrapper: DeviceWrapper[T] | None, value: T
    ) -> None:
        """Send command to the device."""
        if wrapper is None:
            return
        await self._async_send_commands(
            wrapper.get_update_commands(self.device, value),
        )
