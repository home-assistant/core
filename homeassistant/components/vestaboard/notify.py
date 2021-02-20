"""Support for Vestaboard notifications."""
import logging

import vestaboard

from homeassistant.components.notify import ATTR_TARGET, BaseNotificationService

from . import DOMAIN as VESTABOARD_DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Vestaboard notification service."""
    hvbm = hass.data.get(VESTABOARD_DOMAIN)
    return VestaboardNotificationService(hvbm)


class VestaboardNotificationService(BaseNotificationService):
    """Implement the notification service for Vestaboard."""

    def __init__(self, vbm):
        """Initialize the service."""
        self.vbm = vbm
        self._subscriptions = []

    def send_message(self, message="", **kwargs):
        """Send a message to some Vestaboard subscription."""

        targets = kwargs.get(ATTR_TARGET)
        _LOGGER.debug("Targets: %s", targets)

        self._subscriptions = self.vbm.manager.get_subscriptions()

        for board_info in self._subscriptions:
            if targets is None or board_info["_id"] in targets:
                board = vestaboard.Board(
                    apiKey=self.vbm.manager.apiKey,
                    apiSecret=self.vbm.manager.apiSecret,
                    subscriptionId=board_info["_id"],
                )
                try:
                    board.post(message)
                    _LOGGER.debug(
                        "Sent notification to Vestaboard %s", board_info["_id"]
                    )
                except OSError:
                    _LOGGER.warning(
                        "Cannot connect to Vestaboard %s", board_info["_id"]
                    )
