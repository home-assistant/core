"""Base class for Switchbot via API entities."""
import logging
from typing import Any

from homeassistant.helpers.entity import Entity

from .common import Device, Remote
from .const import API, DOMAIN

_LOGGER = logging.getLogger(__name__)


class SwitchbotViaAPIEntity(Entity):
    """Representation of a Switchbot via API entity."""

    _is_remote = False
    _switchbot_state: dict[str, Any] | None = None

    def __init__(self, device: Device | Remote) -> None:
        """Initialize the entity."""
        super().__init__()
        self._attr_unique_id = device.device_id
        self._attr_name = device.device_name
        self._is_remote = isinstance(device, Remote)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.device_id)},
            "name": device.device_name,
            "manufacturer": "Switchbot",
            "model": device.device_type,
        }
        _LOGGER.debug("Initialized %s: %s", self._attr_unique_id, self._attr_name)

    async def send_command(self, command, command_type="command", parameters="default"):
        """Send command to device."""
        return await self.hass.data[DOMAIN][API].send_command(
            self._attr_unique_id,
            command,
            command_type,
            parameters,
        )

    async def async_update(self):
        """Update the entity."""
        if self._is_remote:
            self._switchbot_state = {}
            return
        self._switchbot_state = await self.hass.data[DOMAIN][API].get_status(
            self._attr_unique_id
        )
        _LOGGER.debug(self._switchbot_state)
