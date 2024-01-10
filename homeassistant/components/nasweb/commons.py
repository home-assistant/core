"""Common utility functions for NASweb integration."""

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.components.http import ApiConfig
from homeassistant.core import HomeAssistant

from .const import CONF_HA_ADDRESS, PUSH_API_ENDPOINT
from .coordinator import NotificationCoordinator

_LOGGER = logging.getLogger(__name__)


def initialize_notification_coordinator(
    hass: HomeAssistant,
) -> NotificationCoordinator | None:
    """Initialize and set up NotificationCoordinator instance."""
    notifi_coordinator = NotificationCoordinator()
    try:
        _LOGGER.debug("Adding push notification handler")
        hass.http.app.router.add_post(
            PUSH_API_ENDPOINT, notifi_coordinator.handle_notification
        )
    except RuntimeError:
        _LOGGER.error(
            "Integration cannot register endpoint for local push. "
            "Home Assistant restart should fix this issue"
        )
        return None
    return notifi_coordinator


def get_hass_address_from_entry(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> str | None:
    """Return HA address for use in NASweb push api."""
    hass_address = data.get(CONF_HA_ADDRESS)
    api_config: ApiConfig | None = hass.config.api
    if api_config is None:
        _LOGGER.error("Cannot determine whether to use ssl: hass.config.api is None")
        return None
    if not hass_address:
        return f"{api_config.use_ssl}:{api_config.host}:{api_config.port}"
    return f"{api_config.use_ssl}:{hass_address}"
