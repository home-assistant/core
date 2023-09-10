"""Base class for SwitchBot via API entities."""
import logging
from typing import Any

from switchbot_api import Commands, Device, Remote, SwitchBotAPI

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SwitchBotCoordinator

_LOGGER = logging.getLogger(__name__)


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
        self._attr_name = device.device_name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.device_id)},
            name=device.device_name,
            manufacturer="SwitchBot",
            model=device.device_type,
        )
        _LOGGER.debug("Initialized %s: %s", device.device_id, device.device_name)

    async def send_command(
        self, command: Commands, command_type="command", parameters="default"
    ):
        """Send command to device."""
        return await self._api.send_command(
            self._attr_unique_id,
            command,
            command_type,
            parameters,
        )
