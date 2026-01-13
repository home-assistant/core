"""Mycroft AI notification platform."""

from __future__ import annotations

import logging
from typing import Any

from mycroftapi import MycroftAPI

from homeassistant.components.notify import BaseNotificationService
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MycroftNotificationService:
    """Get the Mycroft notification service."""
    return MycroftNotificationService(hass.data[DOMAIN])


class MycroftNotificationService(BaseNotificationService):
    """The Mycroft Notification Service."""

    def __init__(self, mycroft_ip: str) -> None:
        """Initialize the service."""
        self.mycroft_ip = mycroft_ip

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message mycroft to speak on instance."""

        text = message
        mycroft = MycroftAPI(self.mycroft_ip)
        if mycroft is not None:
            mycroft.speak_text(text)
        else:
            _LOGGER.warning("Could not reach this instance of mycroft")
