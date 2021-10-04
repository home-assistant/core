"""Demo notification service."""
from __future__ import annotations

from typing import Any

from homeassistant.components.notify import BaseNotificationService, NotifyService
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_platform import AddServicesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

EVENT_NOTIFY = "notify"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_services: AddServicesCallback,
) -> None:
    """Set up the Demo config entry."""
    async_add_services([DemoNotifyService()])


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> BaseNotificationService:
    """Get the legacy demo notification service."""
    return LegacyDemoNotificationService()


class DemoNotifyService(NotifyService):
    """Represent a demo notification service."""

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message."""
        kwargs["message"] = message
        self.hass.bus.fire(EVENT_NOTIFY, kwargs)


class LegacyDemoNotificationService(BaseNotificationService):
    """Represent the legacy demo notification service."""

    @property
    def targets(self) -> dict[str, str]:
        """Return a dictionary of registered targets."""
        return {"test target name": "test target id"}

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message."""
        kwargs["message"] = message
        self.hass.bus.fire(EVENT_NOTIFY, kwargs)
