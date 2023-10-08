"""Simplepush notification service."""
from __future__ import annotations

import logging
from typing import Any

from simplepush import BadRequest, UnknownError, send

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.const import CONF_EVENT, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import ATTR_ATTACHMENTS, ATTR_EVENT, CONF_DEVICE_KEY, CONF_SALT

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> SimplePushNotificationService | None:
    """Get the Simplepush notification service."""
    if discovery_info:
        return SimplePushNotificationService(discovery_info)
    return None


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
    event, attachments = self._process_message_data(kwargs)

    try:
        self._send_notification(title, message, attachments, event)
    except BadRequest:
        _LOGGER.error("Bad request. Title or message are too long")
    except UnknownError:
        _LOGGER.error("Failed to send the notification")

def _process_message_data(self, kwargs: Any) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """Process message data from kwargs."""
    data = kwargs.get(ATTR_DATA)
    event, attachments = None, None

    if data:
        event = data.get(ATTR_EVENT)
        attachments_data = data.get(ATTR_ATTACHMENTS)
        if isinstance(attachments_data, list):
            attachments = self._process_attachments(attachments_data)

    return event, attachments

def _process_attachments(self, attachments_data: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Process attachments data."""
    attachments = []
    for attachment in attachments_data:
        if self._is_valid_attachment(attachment):
            attachments.append(self._get_attachment(attachment))
        else:
            _LOGGER.error("Attachment format is incorrect")
    return attachments

def _is_valid_attachment(self, attachment: Dict[str, str]) -> bool:
    """Check if attachment format is valid."""
    return isinstance(attachment, dict) and (
        "image" in attachment or "video" in attachment
        or ("video" in attachment and "thumbnail" in attachment)
    )

def _get_attachment(self, attachment: Dict[str, str]) -> Dict[str, str]:
    """Get the attachment dictionary from the input."""
    if "video" in attachment and "thumbnail" in attachment:
        return attachment
    elif "video" in attachment:
        return attachment["video"]
    elif "image" in attachment:
        return attachment["image"]

def _send_notification(self, title: str, message: str, attachments: List[Dict[str, str]], event: Optional[str]) -> None:
    """Send the Simplepush notification."""
    try:
        if self._password:
            send(
                key=self._device_key,
                password=self._password,
                salt=self._salt,
                title=title,
                message=message,
                attachments=attachments,
                event=event,
            )
        else:
            send(
                key=self._device_key,
                title=title,
                message=message,
                attachments=attachments,
                event=event,
            )
    except BadRequest:
        _LOGGER.error("Bad request. Title or message are too long")
    except UnknownError:
        _LOGGER.error("Failed to send the notification")

