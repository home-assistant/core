"""Subscriber for devolo home control API publisher."""
from collections.abc import Callable
import logging

_LOGGER = logging.getLogger(__name__)


class Subscriber:
    """Subscriber class for the publisher in mprm websocket class."""

    def __init__(self, name: str, callback: Callable) -> None:
        """Initiate the subscriber."""
        self.name = name
        self.callback = callback

    def update(self, message: str) -> None:
        """Trigger hass to update the device."""
        _LOGGER.debug('%s got message "%s"', self.name, message)
        self.callback(message)
