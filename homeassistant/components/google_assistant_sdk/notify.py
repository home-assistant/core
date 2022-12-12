"""Support for Google Assistant SDK broadcast notifications."""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .helpers import async_send_text_commands


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the broadcast notification service."""
    return BroadcastNotificationService(hass)


class BroadcastNotificationService(BaseNotificationService):
    """Implement broadcast notification service."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    async def async_send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message."""
        if not message:
            return

        commands = []
        targets = kwargs.get(ATTR_TARGET)
        if not targets:
            commands.append(f"broadcast {message}")
        else:
            for target in targets:
                commands.append(f"broadcast to {target} {message}")
        await async_send_text_commands(commands, self.hass)
