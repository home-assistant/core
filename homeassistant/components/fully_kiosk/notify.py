"""Support for fully_kiosk notifications."""

from typing import Any

from homeassistant.components.notify import BaseNotificationService
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN
from .coordinator import FullyKioskDataUpdateCoordinator


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService | None:
    """Get the notification service."""
    assert discovery_info
    coordinator: FullyKioskDataUpdateCoordinator = hass.data[DOMAIN][
        discovery_info[CONF_ENTITY_ID]
    ]
    return NotificationService(coordinator)


class NotificationService(BaseNotificationService):
    """Implement notification service."""

    def __init__(self, coordinator: FullyKioskDataUpdateCoordinator) -> None:
        """Initialize the service."""
        self.coordinator = coordinator

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message."""
        await self.coordinator.fully.sendCommand("textToSpeech", text=message)
