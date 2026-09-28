"""Tuya Home Assistant Base Device Model."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, override

from tuya_device_handlers.device_wrapper import DeviceWrapper
from tuya_sharing import CustomerDevice, Manager

from homeassistant.helpers.device_registry import ChildDeviceInfo, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .const import DOMAIN, LOGGER, TUYA_HA_SIGNAL_UPDATE_ENTITY


@dataclass(frozen=True)
class TuyaEntityDescription(EntityDescription):
    """Describes a Tuya entity."""

    channel_index: int | None = None
    channel_condition: Callable[[CustomerDevice], bool] | None = None


def get_child_device_info(
    device: CustomerDevice,
    parent_device_id: str,
    description: TuyaEntityDescription,
) -> ChildDeviceInfo | None:
    """Get the device info for a single channel of a Tuya device.

    Returns None for entities belonging to the device itself, and for devices
    that do not expose more than one channel.
    """
    if (channel_index := description.channel_index) is None:
        return None
    if description.channel_condition and not description.channel_condition(device):
        return None
    return ChildDeviceInfo(
        identifiers={(DOMAIN, f"{device.id}_channel_{channel_index}")},
        parent_device_id=parent_device_id,
        translation_key="channel",
        translation_placeholders={"index": str(channel_index)},
    )


class TuyaEntity(Entity):
    """Tuya base device."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        device: CustomerDevice,
        device_manager: Manager,
        description: TuyaEntityDescription,
        *,
        device_info: ChildDeviceInfo | None = None,
    ) -> None:
        """Init TuyaEntity."""
        self._attr_device_info = device_info or DeviceInfo(
            identifiers={(DOMAIN, device.id)}
        )
        self._attr_unique_id = f"tuya.{device.id}{description.key}"  # pylint: disable=home-assistant-entity-unique-id-redundant-domain
        self.entity_description = description
        # TuyaEntity initialize mq can subscribe
        device.set_up = True
        self.device = device
        self.device_manager = device_manager

    @property
    @override
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device.online

    @override
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
