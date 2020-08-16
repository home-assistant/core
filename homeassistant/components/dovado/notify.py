"""Support for SMS notifications from the Dovado router."""
import logging

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService

from . import DOMAIN as DOVADO_DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Dovado Router SMS notification service."""
    return DovadoSMSNotificationService(hass.data[DOVADO_DOMAIN].client)


class DovadoSMSNotificationService(BaseNotificationService):
    """Implement the notification service for the Dovado SMS component."""

    def __init__(self, client):
        """Initialize the service."""
        self._client = client

    def send_message(self, message, **kwargs):
        """Send SMS to the specified target phone number."""
        target = kwargs.get(ATTR_TARGET)

        if not target:
            _LOGGER.error("One target is required")
            return

        self._client.send_sms(target, message)
