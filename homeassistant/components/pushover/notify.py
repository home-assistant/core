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
    ATTR_TIMESTAMP,
    ATTR_TTL,
    ATTR_URL,
    ATTR_URL_TITLE,
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
        self, hass: HomeAssistant, entry: Any, creds: Any = None, platform: Any = None
    ) -> None:
        """Initialize the service.

        Supports new-style (hass, PushoverAPI, user_key)
        and legacy (hass, entry, creds, platform) signatures.
        """
        # New vs legacy: creds is a dict in legacy mode
        if not isinstance(creds, dict):
            # New (config-entry) style: entry is PushoverAPI, creds is user_key
            pushover = entry
            user_key = creds
        else:
            # Legacy style: entry is ignored, creds is the dict of credentials
            creds_dict = creds or {}
            app_token = creds_dict.get("app_token")
            user_key = creds_dict.get("user_key")
            pushover = PushoverAPI(app_token) if app_token is not None else None
        # After determining pushover and user_key, save them for send_message
        self.hass = hass
        self._hass = hass
        self._user_key = user_key
        self.pushover = pushover

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        # Extract params from data dict
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        data = dict(kwargs.get(ATTR_DATA) or {})
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
            self.pushover.send_message(
                self._user_key,
                message,
                ",".join(kwargs.get(ATTR_TARGET, [])),
                title,
                url,
                url_title,
                image,
                priority,
                retry,
                expire,
                callback_url,
                timestamp,
                sound,
                html,
                ttl,
            )

        except BadAPIRequestError as err:
            raise HomeAssistantError(str(err)) from err
