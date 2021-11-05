"""Provide a mock notify platform."""
from typing import Any

from homeassistant.components.notify import NotifyService
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_platform import AddServicesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_services: AddServicesCallback
) -> None:
    """Set up the notify platform."""
    async_add_services([NotificationService()])


class NotificationService(NotifyService):
    """A test class for notification services."""

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
