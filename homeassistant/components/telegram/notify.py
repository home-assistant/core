"""Telegram platform for notify component."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TARGET,
    ATTR_TITLE,
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.components.telegram_bot import (
    ATTR_DISABLE_NOTIF,
    ATTR_DISABLE_WEB_PREV,
    ATTR_MESSAGE_TAG,
    ATTR_MESSAGE_THREAD_ID,
    ATTR_PARSER,
)
from homeassistant.const import ATTR_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.reload import setup_reload_service
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import DOMAIN as TELEGRAM_DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

DOMAIN = "telegram_bot"
ATTR_KEYBOARD = "keyboard"
ATTR_INLINE_KEYBOARD = "inline_keyboard"
ATTR_PHOTO = "photo"
ATTR_VIDEO = "video"
ATTR_VOICE = "voice"
ATTR_DOCUMENT = "document"

CONF_CHAT_ID = "chat_id"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_CHAT_ID): vol.Coerce(int)}
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None,
) -> TelegramNotificationService:
    """Get the Telegram notification service."""
    setup_reload_service(hass, TELEGRAM_DOMAIN, PLATFORMS)

    # chat_id can either come from configuration.yaml or from discovery (config flow)
    chat_id: Any = (
        discovery_info[CONF_CHAT_ID] if discovery_info else config.get(CONF_CHAT_ID)
    )

    return TelegramNotificationService(hass, int(chat_id))


class TelegramNotificationService(BaseNotificationService):
    """Implement the notification service for Telegram."""

    def __init__(self, hass: HomeAssistant, chat_id: int) -> None:
        """Initialize the service."""
        self._chat_id = chat_id
        self.hass = hass

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        service_data = {ATTR_TARGET: kwargs.get(ATTR_TARGET, self._chat_id)}
        if ATTR_TITLE in kwargs:
            service_data.update({ATTR_TITLE: kwargs.get(ATTR_TITLE)})
        if message:
            service_data.update({ATTR_MESSAGE: message})
        data = kwargs.get(ATTR_DATA)

        # Set message tag
        if data is not None and ATTR_MESSAGE_TAG in data:
            message_tag = data.get(ATTR_MESSAGE_TAG)
            service_data.update({ATTR_MESSAGE_TAG: message_tag})

        # Set disable_notification
        if data is not None and ATTR_DISABLE_NOTIF in data:
            disable_notification = data.get(ATTR_DISABLE_NOTIF)
            service_data.update({ATTR_DISABLE_NOTIF: disable_notification})

        # Set parse_mode
        if data is not None and ATTR_PARSER in data:
            parse_mode = data.get(ATTR_PARSER)
            service_data.update({ATTR_PARSER: parse_mode})

        # Set disable_web_page_preview
        if data is not None and ATTR_DISABLE_WEB_PREV in data:
            disable_web_page_preview = data[ATTR_DISABLE_WEB_PREV]
            service_data.update({ATTR_DISABLE_WEB_PREV: disable_web_page_preview})

        # Set message_thread_id
        if data is not None and ATTR_MESSAGE_THREAD_ID in data:
            message_thread_id = data[ATTR_MESSAGE_THREAD_ID]
            service_data.update({ATTR_MESSAGE_THREAD_ID: message_thread_id})

        # Get keyboard info
        if data is not None and ATTR_KEYBOARD in data:
            keys = data.get(ATTR_KEYBOARD)
            keys = keys if isinstance(keys, list) else [keys]
            service_data.update(keyboard=keys)
        elif data is not None and ATTR_INLINE_KEYBOARD in data:
            keys = data.get(ATTR_INLINE_KEYBOARD)
            keys = keys if isinstance(keys, list) else [keys]
            service_data.update(inline_keyboard=keys)

        # Send a photo, video, document, voice, or location
        if data is not None and ATTR_PHOTO in data:
            photos = data.get(ATTR_PHOTO)
            photos = photos if isinstance(photos, list) else [photos]
            for photo_data in photos:
                service_data.update(photo_data)
                self.hass.services.call(DOMAIN, "send_photo", service_data=service_data)
            return None
        if data is not None and ATTR_VIDEO in data:
            videos = data.get(ATTR_VIDEO)
            videos = videos if isinstance(videos, list) else [videos]
            for video_data in videos:
                service_data.update(video_data)
                self.hass.services.call(DOMAIN, "send_video", service_data=service_data)
            return None
        if data is not None and ATTR_VOICE in data:
            voices = data.get(ATTR_VOICE)
            voices = voices if isinstance(voices, list) else [voices]
            for voice_data in voices:
                service_data.update(voice_data)
                self.hass.services.call(DOMAIN, "send_voice", service_data=service_data)
            return None
        if data is not None and ATTR_LOCATION in data:
            service_data.update(data.get(ATTR_LOCATION))
            return self.hass.services.call(
                DOMAIN, "send_location", service_data=service_data
            )
        if data is not None and ATTR_DOCUMENT in data:
            service_data.update(data.get(ATTR_DOCUMENT))
            return self.hass.services.call(
                DOMAIN, "send_document", service_data=service_data
            )

        # Send message
        _LOGGER.debug(
            "TELEGRAM NOTIFIER calling %s.send_message with %s", DOMAIN, service_data
        )
        return self.hass.services.call(
            DOMAIN, "send_message", service_data=service_data
        )
