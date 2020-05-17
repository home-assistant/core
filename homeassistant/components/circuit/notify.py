"""Unify Circuit platform for notify component."""
import logging

from circuit_webhook import Circuit
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import CONF_URL
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_URL): cv.url})


def get_service(hass, config, discovery_info=None):
    """Get the Unify Circuit notification service."""
    webhook_url = config.get(CONF_URL)

    try:
        return CircuitNotificationService(webhook_url)

    except RuntimeError as err:
        _LOGGER.exception("Error in creating a new Unify Circuit message: %s", err)
        return None


class CircuitNotificationService(BaseNotificationService):
    """Implement the notification service for Unify Circuit."""

    def __init__(self, webhook_url):
        """Initialize the service."""
        self._webhook_url = webhook_url

    def send_message(self, message=None, **kwargs):
        """Send a message to the webhook."""

        circuit_message = Circuit(url=self._webhook_url)

        try:
            circuit_message.post(text=message)
        except RuntimeError as err:
            _LOGGER.error("Could not send notification. Error: %s", err)
