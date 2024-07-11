"""Base class for SwitchBot via API entities."""

from typing import Any

from switchbot_api import Commands, Device, Remote, SwitchBotAPI

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator


class SwitchBotCloudEntity(CoordinatorEntity[SwitchBotCoordinator]):
    """Representation of a SwitchBot Cloud entity."""

    _api: SwitchBotAPI
    _switchbot_state: dict[str, Any] | None = None
    _attr_has_entity_name = True

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: SwitchBotCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._api = api
        self._attr_unique_id = device.device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer="SwitchBot",
            model=device.device_type,
        )

    async def send_command(
        self,
        command: Commands,
        command_type: str = "command",
        parameters: dict | str = "default",
    ) -> None:
        """Send command to device."""
        await self._api.send_command(
            self._attr_unique_id,
            command,
            command_type,
            parameters,
        )
