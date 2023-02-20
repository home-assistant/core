"""Demo notification service."""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import BaseNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

EVENT_NOTIFY = "notify"


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the demo notification service."""
    return DemoNotificationService(hass)


class DemoNotificationService(BaseNotificationService):
    """Implement demo notification service."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the service."""
        self.hass = hass

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {"test target name": "test target id"}

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        kwargs["message"] = message
        self.hass.bus.fire(EVENT_NOTIFY, kwargs)
