"""Unify Circuit platform for notify component."""

from __future__ import annotations

import logging

from circuit_webhook import Circuit

from homeassistant.components.notify import BaseNotificationService
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> CircuitNotificationService | None:
    """Get the Unify Circuit notification service."""
    if discovery_info is None:
        return None

    return CircuitNotificationService(discovery_info)


class CircuitNotificationService(BaseNotificationService):
    """Implement the notification service for Unify Circuit."""

    def __init__(self, config):
        """Initialize the service."""
        self.webhook_url = config[CONF_URL]

    def send_message(self, message=None, **kwargs):
        """Send a message to the webhook."""

        webhook_url = self.webhook_url

        if webhook_url and message:
            try:
                circuit_message = Circuit(url=webhook_url)
                circuit_message.post(text=message)
            except RuntimeError as err:
                _LOGGER.error("Could not send notification. Error: %s", err)
