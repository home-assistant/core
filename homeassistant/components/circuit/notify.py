"""Unify Circuit platform for notify component."""
import logging

import attr
from circuit_webhook import Circuit

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService
from homeassistant.const import CONF_URL

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Unify Circuit notification service."""
    if discovery_info is None:
        return None

    return CircuitNotificationService(hass, discovery_info)


@attr.s
class CircuitNotificationService(BaseNotificationService):
    """Implement the notification service for Unify Circuit."""

    hass = attr.ib()
    config = attr.ib()

    def send_message(self, message=None, **kwargs):
        """Send a message to the webhook."""

        webhook_url = self.config[CONF_URL]
        targets = kwargs.get(ATTR_TARGET, webhook_url)

        if targets and message:
            for target in targets:
                try:
                    circuit_message = Circuit(url=target)
                    circuit_message.post(text=message)
                except RuntimeError as err:
                    _LOGGER.error("Could not send notification. Error: %s", err)
