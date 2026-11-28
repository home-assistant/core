"""Common entity for VeSync Component."""

from collections.abc import Awaitable
from typing import override

from pyvesync.base_devices.vesyncbasedevice import VeSyncBaseDevice
from pyvesync.const import ConnectionStatus
from pyvesync.utils.errors import VeSyncError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VeSyncDataCoordinator


class VeSyncBaseEntity[T: VeSyncBaseDevice](CoordinatorEntity[VeSyncDataCoordinator]):
    """Base class for VeSync Entity Representations."""

    _attr_has_entity_name = True

    def __init__(self, device: T, coordinator: VeSyncDataCoordinator) -> None:
        """Initialize the VeSync device."""
        super().__init__(coordinator)
        self.device = device
        self._attr_unique_id = self.base_unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.base_unique_id)},
            name=self.device.device_name,
            model=self.device.device_type,
            manufacturer="VeSync",
            sw_version=self.device.current_firm_version,
        )

    @property
    def base_unique_id(self) -> str:
        """Return the ID of this device."""
        # The unique_id property may be overridden in subclasses, such as in
        # sensors. Maintaining base_unique_id allows us to group related
        # entities under a single device.
        if isinstance(self.device.sub_device_no, int):
            return f"{self.device.cid}{self.device.sub_device_no!s}"
        return self.device.cid

    @property
    @override
    def available(self) -> bool:
        """Return True if device is available."""
        return (
            super().available
            and self.device.state.connection_status == ConnectionStatus.ONLINE
        )

    async def _async_send_command(self, command: Awaitable[bool]) -> None:
        """Await a device command and raise if it fails."""
        # Drop the previous call's response so a stale message is never shown
        self.device.last_response = None
        try:
            success = await command
        except VeSyncError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_response_error"
            ) from err
        if success:
            return
        # The VeSync message is untranslated, but often explains the failure
        if (response := self.device.last_response) is not None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"message": response.message},
            )
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="command_failed_no_response"
        )
