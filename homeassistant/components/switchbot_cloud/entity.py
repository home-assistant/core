"""Base class for SwitchBot via API entities."""
import logging
from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SwitchBotCloudEntity(CoordinatorEntity):
    """Representation of a SwitchBot Cloud entity."""

    _api: SwitchBotAPI
    _SwitchBot_state: dict[str, Any] | None = None

    def __init__(
        self,
        api: SwitchBotAPI,
        device: Device | Remote,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator=coordinator)
        self._api = api
        self._attr_unique_id = device.device_id
        self._attr_name = device.device_name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.device_name,
            "manufacturer": "SwitchBot",
            "model": device.device_type,
        }
        _LOGGER.debug("Initialized %s: %s", self._attr_unique_id, self._attr_name)

    async def send_command(self, command, command_type="command", parameters="default"):
        """Send command to device."""
        return await self._api.send_command(
            self._attr_unique_id,
            command,
            command_type,
            parameters,
        )
