"""Helper functions for NASweb integration."""

import logging

from homeassistant.core import HomeAssistant

from .const import PUSH_API_ENDPOINT
from .coordinator import NotificationCoordinator

_LOGGER = logging.getLogger(__name__)


def initialize_notification_coordinator(
    hass: HomeAssistant,
) -> NotificationCoordinator | None:
    """Initialize and set up NotificationCoordinator instance."""
    notify_coordinator = NotificationCoordinator()
    try:
        _LOGGER.debug("Adding push notification handler")
        hass.http.app.router.add_post(
            PUSH_API_ENDPOINT, notify_coordinator.handle_notification
        )
    except RuntimeError:
        _LOGGER.error(
            "Integration cannot register endpoint for local push. "
            "Home Assistant restart should fix this issue"
        )
        return None
    return notify_coordinator
