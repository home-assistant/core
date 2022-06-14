"""Simplepush notification service."""
from __future__ import annotations

import logging
from typing import Any

from simplepush import send, send_encrypted
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.notify.const import ATTR_DATA, DOMAIN as NOTIFY_DOMAIN
from homeassistant.const import CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_ENCRYPTED, ATTR_EVENT, CONF_DEVICE_KEY, CONF_SALT

# Configuring simplepsuh under the notify platform will be deprecated in 2022.8.0
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_DEVICE_KEY): cv.string,
        vol.Optional(CONF_EVENT): cv.string,
        vol.Inclusive(CONF_PASSWORD, ATTR_ENCRYPTED): cv.string,
        vol.Inclusive(CONF_SALT, ATTR_ENCRYPTED): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if discovery_info:
        return SimplePushNotificationService(discovery_info)

    _LOGGER.warning(
        "Manually configured simplepush integration found under platform key '%s'. "
        "Please remove and configure through the UI",
        NOTIFY_DOMAIN,
    )
    return SimplePushNotificationService(config)


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

        # event can now be passwed in the service data
        event = None
        if data := kwargs.get(ATTR_DATA):
            event = data.get(ATTR_EVENT)

        # use event from config until YAML config is removed
        event = event or self._event

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
