"""Base entity for GARDENA smart local."""

from typing import override

from gardena_smart_local_api.devices.device import Device
from gardena_smart_local_api.messages import EgressMessageList, Reply

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import COMMAND_REPLY_TIMEOUT, GardenaSmartLocalCoordinator


def find_device_subentry_id(entry: ConfigEntry, device_id: str) -> str | None:
    """Return the subentry id that a device belongs to, if any."""
    return next(
        (
            sid
            for sid, se in entry.subentries.items()
            if se.data.get("device_id") == device_id
        ),
        None,
    )


class GardenaEntity(CoordinatorEntity[GardenaSmartLocalCoordinator]):
    """Base entity for a GARDENA smart local device."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GardenaSmartLocalCoordinator,
        device: Device,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._device = device
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            name=f"GARDENA {device.model_definition.name} {device.serial_number}",
            manufacturer="GARDENA",
            model=device.model_definition.name,
            model_id=device.model_definition.model_number,
            sw_version=device.software_version,
            hw_version=device.hardware_version,
            serial_number=device.serial_number,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True if the gateway is connected and the device is online."""
        if not self.coordinator.connected:
            return False
        device = self.coordinator.data.get(self._device.id)
        return bool(device and device.is_online)

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Keep the device registry sw_version in sync.

        DeviceInfo is only applied when the entity is added, so after a
        firmware up-/downgrade the device page would keep showing the old
        version until Home Assistant restarts.
        """
        device = self.coordinator.data.get(self._device.id)
        if (
            device
            and device.software_version
            and self.device_entry
            and self.device_entry.sw_version != device.software_version
        ):
            dr.async_get(self.hass).async_update_device(
                self.device_entry.id, sw_version=device.software_version
            )
        super()._handle_coordinator_update()

    async def _send_confirmed_command(
        self, request: EgressMessageList, timeout_sec: float = COMMAND_REPLY_TIMEOUT
    ) -> None:
        """Send a command and wait for the gateway to confirm it landed.

        Raises HomeAssistantError on timeout or rejection instead of letting
        the entity's state flip based on unconfirmed intermediate frames.
        """
        try:
            replies = await self.coordinator.send_request(
                self._device.id, request, wait_for_response_sec=timeout_sec
            )
        except TimeoutError as err:
            raise HomeAssistantError(
                f"Timed out waiting for the GARDENA smart Gateway to confirm "
                f"the command for device {self._device.id}"
            ) from err

        for msg in replies:
            if isinstance(msg, Reply) and not msg.success:
                raise HomeAssistantError(
                    f"GARDENA smart Gateway rejected the command for device "
                    f"{self._device.id}"
                )
