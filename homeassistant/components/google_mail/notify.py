"""Notification service for Google Mail integration."""
from __future__ import annotations

import base64
from email.message import EmailMessage
from typing import Any

from googleapiclient.http import HttpRequest

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .api import AsyncConfigEntryAuth
from .const import ATTR_BCC, ATTR_CC, ATTR_FROM, ATTR_ME, ATTR_SEND, DATA_AUTH


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> GMailNotificationService | None:
    """Get the notification service."""
    return GMailNotificationService(discovery_info) if discovery_info else None


class GMailNotificationService(BaseNotificationService):
    """Define the Google Mail notification logic."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initialize the service."""
        self.auth: AsyncConfigEntryAuth = config[DATA_AUTH]

    async def async_send_message(self, message: str, **kwargs: Any) -> None:
        """Send a message."""
        data: dict[str, Any] = kwargs.get(ATTR_DATA) or {}
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        email = EmailMessage()
        email.set_content(message)
        if to_addrs := kwargs.get(ATTR_TARGET):
            email["To"] = ", ".join(to_addrs)
        email["From"] = data.get(ATTR_FROM, ATTR_ME)
        email["Subject"] = title
        email[ATTR_CC] = ", ".join(data.get(ATTR_CC, []))
        email[ATTR_BCC] = ", ".join(data.get(ATTR_BCC, []))

        encoded_message = base64.urlsafe_b64encode(email.as_bytes()).decode()
        body = {"raw": encoded_message}
        msg: HttpRequest
        users = (await self.auth.get_resource()).users()
        if data.get(ATTR_SEND) is False:
            msg = users.drafts().create(userId=email["From"], body={ATTR_MESSAGE: body})
        else:
            if not to_addrs:
                raise ValueError("recipient address required")
            msg = users.messages().send(userId=email["From"], body=body)
        await self.hass.async_add_executor_job(msg.execute)
