"""MessageBird platform for notify component."""

import logging
from typing import Any, override

import messagebird
from messagebird.client import ErrorException
import probatio

from homeassistant.components.notify import (
    ATTR_TARGET,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_SENDER
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "message_bird"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): cv.string,
        probatio.Optional(CONF_SENDER, default="HA"): probatio.All(
            cv.string, probatio.Match(r"^(\+?[1-9]\d{1,14}|\w{1,11})$")
        ),
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> MessageBirdNotificationService | None:
    """Get the MessageBird notification service."""
    client = messagebird.Client(config[CONF_API_KEY])
    try:
        # validates the api key
        client.balance()
    except messagebird.client.ErrorException:
        _LOGGER.error("The specified MessageBird API key is invalid")
        return None

    return MessageBirdNotificationService(config.get(CONF_SENDER), client)


class MessageBirdNotificationService(BaseNotificationService):
    """Implement the notification service for MessageBird."""

    def __init__(self, sender, client):
        """Initialize the service."""
        self.sender = sender
        self.client = client

    @override
    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a specified target."""
        if not (targets := kwargs.get(ATTR_TARGET)):
            _LOGGER.error("No target specified")
            return

        failed_targets: list[str] = []
        for target in targets:
            try:
                self.client.message_create(
                    self.sender, target, message, {"reference": "HA"}
                )
            except ErrorException as err:
                _LOGGER.debug("Failed to notify %s: %s", target, err)
                failed_targets.append(target)

        if failed_targets:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_message_failed",
                translation_placeholders={"targets": ", ".join(failed_targets)},
            )
