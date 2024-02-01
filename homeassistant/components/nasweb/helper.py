"""Helper functions for NASweb integration."""

import logging

from aiohttp.hdrs import METH_POST

from homeassistant.components.webhook import (
    async_generate_id,
    async_register as webhook_register,
    async_unregister as webhook_unregister,
)
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.network import get_url

from .const import DOMAIN, NOTIFY_COORDINATOR, WEBHOOK_URL
from .coordinator import NotificationCoordinator

_LOGGER = logging.getLogger(__name__)


def get_integration_webhook_url(hass: HomeAssistant) -> str:
    """Return webhook url for Push API."""
    hass_url = get_url(hass)
    return WEBHOOK_URL.format(
        internal_url=hass_url, webhook_id=hass.data[DOMAIN][CONF_WEBHOOK_ID]
    )


def initialize_notification_coordinator(hass: HomeAssistant) -> NotificationCoordinator:
    """Initialize and set up NotificationCoordinator instance."""
    if NOTIFY_COORDINATOR not in hass.data[DOMAIN]:
        hass.data[DOMAIN][NOTIFY_COORDINATOR] = NotificationCoordinator()
    notify_coordinator: NotificationCoordinator = hass.data[DOMAIN][NOTIFY_COORDINATOR]
    if CONF_WEBHOOK_ID not in hass.data[DOMAIN]:
        hass.data[DOMAIN][CONF_WEBHOOK_ID] = async_generate_id()
        webhook_register(
            hass,
            DOMAIN,
            "NASweb",
            hass.data[DOMAIN][CONF_WEBHOOK_ID],
            notify_coordinator.handle_webhook_request,
            allowed_methods=[METH_POST],
        )
        _LOGGER.debug("Registered webhook: %s", hass.data[DOMAIN][CONF_WEBHOOK_ID])
    return notify_coordinator


def deinitialize_notification_coordinator_if_empty(hass: HomeAssistant) -> None:
    """Deinitialize NotificationCoordinator instance when no longer needed."""
    notify_coordinator: NotificationCoordinator | None = hass.data[DOMAIN].get(
        NOTIFY_COORDINATOR
    )
    if notify_coordinator is not None and not notify_coordinator.has_coordinators():
        hass.data[DOMAIN].pop(NOTIFY_COORDINATOR)
        webhook_id: str = hass.data[DOMAIN].pop(CONF_WEBHOOK_ID)
        webhook_unregister(hass, webhook_id)
        _LOGGER.debug("Deinitialized Notification Coordinator")
