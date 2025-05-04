"""Pushover platform for notify component."""

from __future__ import annotations

import logging
from typing import Any

from pushover_complete import BadAPIRequestError, PushoverAPI

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    BaseNotificationService,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import (
    ATTR_ATTACHMENT,
    ATTR_CALLBACK_URL,
    ATTR_EXPIRE,
    ATTR_HTML,
    ATTR_PRIORITY,
    ATTR_RETRY,
    ATTR_SOUND,
    ATTR_TAGS,
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URL,
    ATTR_URL_TITLE,
    CLEAR_NOTIFICATIONS_BY_TAGS,
    CONF_USER_KEY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> PushoverNotificationService | None:
    """Get the Pushover notification service."""
    if discovery_info is None:
        return None
    pushover_api: PushoverAPI = hass.data[DOMAIN][discovery_info["entry_id"]]
    return PushoverNotificationService(
        hass, pushover_api, discovery_info[CONF_USER_KEY]
    )


class PushoverNotificationService(BaseNotificationService):
    """Implement the notification service for Pushover."""

    def __init__(
        self, hass: HomeAssistant, pushover: PushoverAPI, user_key: str
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._user_key = user_key
        self.pushover = pushover
        self.receipt_tags: dict[str, list[str]] = {}

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = kwargs.get(ATTR_DATA, {})
        url = data.get(ATTR_URL)
        url_title = data.get(ATTR_URL_TITLE)
        priority = data.get(ATTR_PRIORITY)
        retry = data.get(ATTR_RETRY)
        expire = data.get(ATTR_EXPIRE)
        ttl = data.get(ATTR_TTL)
        callback_url = data.get(ATTR_CALLBACK_URL)
        timestamp = data.get(ATTR_TIMESTAMP)
        sound = data.get(ATTR_SOUND)
        html = 1 if data.get(ATTR_HTML, False) else 0
        tags = data.get(ATTR_TAGS, "")

        if message == CLEAR_NOTIFICATIONS_BY_TAGS and tags != "":
            return self.clear_notification(tags)

        # Check for attachment
        if (image := data.get(ATTR_ATTACHMENT)) is not None:
            # Only allow attachments from whitelisted paths, check valid path
            if self._hass.config.is_allowed_path(data[ATTR_ATTACHMENT]):
                # try to open it as a normal file.
                try:
                    # pylint: disable-next=consider-using-with
                    file_handle = open(data[ATTR_ATTACHMENT], "rb")
                    # Replace the attachment identifier with file object.
                    image = file_handle
                except OSError as ex_val:
                    _LOGGER.error(ex_val)
                    # Remove attachment key to send without attachment.
                    image = None
            else:
                _LOGGER.error("Path is not whitelisted")
                # Remove attachment key to send without attachment.
                image = None

        try:
            result = self.pushover.send_message(
                user=self._user_key,
                message=message,
                device=",".join(kwargs.get(ATTR_TARGET, [])),
                title=title,
                url=url,
                url_title=url_title,
                image=image,
                priority=priority,
                retry=retry,
                expire=expire,
                callback_url=callback_url,
                timestamp=timestamp,
                sound=sound,
                html=html,
                ttl=ttl,
            )
            if "receipt" in result and tags:
                self.receipt_tags[result["receipt"]] = tags.split(",")

        except BadAPIRequestError as err:
            raise HomeAssistantError(str(err)) from err

    def clear_notification(self, tags: str):
        """Cancel any priority 2 message formerly tagged with any of the given tags.

        The tags may contain multiple comma-separated entries in which case all
        notification that are tagged with at least one of the items are cleared.
        """
        _LOGGER.debug("Attempting to clear all notifications tagged with: %s", tags)
        receipts: list[str] = []
        for tag in tags.split(","):
            for receipt, msg_tags in self.receipt_tags.items():
                if tag in msg_tags:
                    receipts.append(receipt)
        for receipt in receipts:
            try:
                self.pushover.cancel_receipt(receipt)
            except BadAPIRequestError:
                _LOGGER.exception("Error while trying to cancel receipt %s", receipt)
            del self.receipt_tags[receipt]
