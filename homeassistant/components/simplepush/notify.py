"""Simplepush notification service."""
from __future__ import annotations

import logging
from typing import Any

from simplepush import BadRequest, UnknownError, send, send_encrypted

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA as BASE_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.notify.const import ATTR_DATA
from homeassistant.const import CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_EVENT, CONF_DEVICE_KEY, CONF_SALT, DOMAIN

# Configuring Simplepush under the notify has been removed in 2022.9.0
PLATFORM_SCHEMA = BASE_PLATFORM_SCHEMA

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if discovery_info is None:
        async_create_issue(
            hass,
            DOMAIN,
            "removed_yaml",
            breaks_in_ha_version="2022.9.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="removed_yaml",
        )
        return None

    return SimplePushNotificationService(discovery_info)


class SimplePushNotificationService(BaseNotificationService):
    """Implementation of the notification service for Simplepush."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the Simplepush notification service."""
        self._device_key: str = config[CONF_DEVICE_KEY]
        self._event: str | None = config.get(CONF_EVENT)
        self._password: str | None = config.get(CONF_PASSWORD)
        self._salt: str | None = config.get(CONF_SALT)

    def send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message to a Simplepush user."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        # event can now be passed in the service data
        event = None
        if data := kwargs.get(ATTR_DATA):
            event = data.get(ATTR_EVENT)

        # use event from config until YAML config is removed
        event = event or self._event

        try:
            if self._password:
                send_encrypted(
                    self._device_key,
                    self._password,
                    self._salt,
                    title,
                    message,
                    event=event,
                )
            else:
                send(self._device_key, title, message, event=event)

        except BadRequest:
            _LOGGER.error("Bad request. Title or message are too long")
        except UnknownError:
            _LOGGER.error("Failed to send the notification")
