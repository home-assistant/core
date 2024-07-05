"""The Telegram client integration."""

from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient, events
from telethon.errors.common import AuthKeyNotFound
from telethon.errors.rpcbaseerrors import AuthKeyError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_API_HASH,
    CONF_API_ID,
    CONF_PHONE_NUMBER,
    CONF_SESSION_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_SEND_MESSAGE = "send_message"

ATTR_DATA = "data"
ATTR_DEVICE_ID = "device_id"
ATTR_MESSAGE = "message"
ATTR_TITLE = "title"

ATTR_ARGS = "args"
ATTR_AUTHENTICATION = "authentication"
ATTR_CALLBACK_QUERY = "callback_query"
ATTR_CALLBACK_QUERY_ID = "callback_query_id"
ATTR_CAPTION = "caption"
ATTR_CHAT_ID = "chat_id"
ATTR_CHAT_INSTANCE = "chat_instance"
ATTR_DATE = "date"
ATTR_DISABLE_NOTIF = "disable_notification"
ATTR_DISABLE_WEB_PREV = "disable_web_page_preview"
ATTR_EDITED_MSG = "edited_message"
ATTR_FILE = "file"
ATTR_FROM_FIRST = "from_first"
ATTR_FROM_LAST = "from_last"
ATTR_KEYBOARD = "keyboard"
ATTR_RESIZE_KEYBOARD = "resize_keyboard"
ATTR_ONE_TIME_KEYBOARD = "one_time_keyboard"
ATTR_KEYBOARD_INLINE = "inline_keyboard"
ATTR_MESSAGEID = "message_id"
ATTR_MSG = "message"
ATTR_MSGID = "id"
ATTR_PARSER = "parse_mode"
ATTR_PASSWORD = "password"
ATTR_REPLY_TO_MSGID = "reply_to_message_id"
ATTR_REPLYMARKUP = "reply_markup"
ATTR_SHOW_ALERT = "show_alert"
ATTR_STICKER_ID = "sticker_id"
ATTR_TARGET_USERNAME = "target_username"
ATTR_TARGET_ID = "target_id"
ATTR_TEXT = "text"
ATTR_URL = "url"
ATTR_USER_ID = "user_id"
ATTR_USERNAME = "username"
ATTR_VERIFY_SSL = "verify_ssl"
ATTR_TIMEOUT = "timeout"
ATTR_MESSAGE_TAG = "message_tag"
ATTR_CHANNEL_POST = "channel_post"
ATTR_SCHEDULE = "schedule"
ATTR_QUESTION = "question"
ATTR_OPTIONS = "options"
ATTR_ANSWERS = "answers"
ATTR_OPEN_PERIOD = "open_period"
ATTR_IS_ANONYMOUS = "is_anonymous"
ATTR_ALLOWS_MULTIPLE_ANSWERS = "allows_multiple_answers"
ATTR_MESSAGE_THREAD_ID = "message_thread_id"


def _has_only_one_target_kind(conf: dict[str, Any]) -> dict[str, Any]:
    error_msg = "You should specify either target_id or target_username but not both"
    if ATTR_TARGET_USERNAME in conf and ATTR_TARGET_ID in conf:
        raise vol.Invalid(error_msg)
    if ATTR_TARGET_USERNAME not in conf and ATTR_TARGET_ID not in conf:
        raise vol.Invalid(error_msg)
    return conf


def _date_is_in_future(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    value = dt_util.as_local(value)
    if value <= dt_util.now():
        raise vol.Invalid("Schedule date should be in future")
    return value


BASE_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_TARGET_USERNAME): cv.string,
        vol.Optional(ATTR_TARGET_ID): int,
        vol.Optional(ATTR_PARSER): cv.string,
        vol.Optional(ATTR_DISABLE_NOTIF): cv.boolean,
        vol.Optional(ATTR_DISABLE_WEB_PREV): cv.boolean,
        vol.Optional(ATTR_RESIZE_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_ONE_TIME_KEYBOARD): cv.boolean,
        vol.Optional(ATTR_KEYBOARD): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_KEYBOARD_INLINE): cv.ensure_list,
        vol.Optional(ATTR_TIMEOUT): cv.positive_int,
        vol.Optional(ATTR_MESSAGE_TAG): cv.string,
        vol.Optional(ATTR_REPLY_TO_MSGID): cv.positive_int,
        vol.Optional(ATTR_SCHEDULE): vol.All(cv.datetime, _date_is_in_future),
    },
    extra=vol.ALLOW_EXTRA,
)

SEND_MESSAGE_SCHEMA = vol.Schema(
    vol.All(
        BASE_SERVICE_SCHEMA.extend(
            {
                vol.Required(ATTR_MESSAGE): cv.string,
            }
        ),
        _has_only_one_target_kind,
    )
)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Telegram client component."""

    async def async_telegram_call(call: ServiceCall) -> None:
        """Process Telegram service call."""
        device_id = call.data[ATTR_DEVICE_ID]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get(device_id)
        if not device:
            return
        telegram_client_entry: TelegramClientEntry = hass.data[DOMAIN].get(
            device.primary_config_entry
        )
        client = telegram_client_entry.client
        config = telegram_client_entry.config

        service = call.service
        target = call.data.get(ATTR_TARGET_USERNAME) or call.data.get(ATTR_TARGET_ID)
        reply_to = call.data.get(ATTR_REPLY_TO_MSGID)
        parse_mode = call.data.get(ATTR_PARSER)
        link_preview = not call.data.get(ATTR_DISABLE_WEB_PREV, False)
        silent = call.data.get(ATTR_DISABLE_NOTIF)
        schedule = call.data.get(ATTR_SCHEDULE)

        try:
            if service == SERVICE_SEND_MESSAGE:
                message = call.data[ATTR_MESSAGE]
                await client.send_message(
                    target,
                    message,
                    reply_to=reply_to,
                    parse_mode=parse_mode,
                    link_preview=link_preview,
                    silent=silent,
                    schedule=schedule,
                )
        except (AuthKeyError, AuthKeyNotFound) as ex:
            await client.log_out()
            raise ConfigEntryAuthFailed(
                f"Credentials expired for {config.data[CONF_PHONE_NUMBER]}"
            ) from ex

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, async_telegram_call, schema=SEND_MESSAGE_SCHEMA
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Handle Telegram client entry setup."""
    telegram_client_entry = TelegramClientEntry(hass, config)
    client = telegram_client_entry.client
    try:
        await client.connect()
        if await client.is_user_authorized():
            await client.start(config.data[CONF_PHONE_NUMBER])
        else:
            raise AuthKeyNotFound
    except (AuthKeyError, AuthKeyNotFound) as ex:
        await client.log_out()
        raise ConfigEntryAuthFailed(
            f"Credentials expired for {config.data[CONF_PHONE_NUMBER]}"
        ) from ex
    return client.is_connected()


async def async_unload_entry(hass: HomeAssistant, config: ConfigEntry) -> bool:
    """Unload a config entry."""
    if config.entry_id in hass.data[DOMAIN]:
        client = hass.data[DOMAIN][config.entry_id].client
        await client.disconnect()
        del hass.data[DOMAIN][config.entry_id]
        return not client.is_connected()

    return True


async def async_remove_entry(hass: HomeAssistant, config: ConfigEntry) -> None:
    """Handle removal of an entry."""
    await async_unload_entry(hass, config)


class TelegramClientEntry:
    """Telegram client entry class."""

    _client: TelegramClient
    _config: ConfigEntry

    def __init__(self, hass: HomeAssistant, config: ConfigEntry) -> None:
        """Init."""
        self._config = config
        self._client = TelegramClient(
            Path(
                hass.config.path(
                    STORAGE_DIR, DOMAIN, f"{self.config.data[CONF_SESSION_ID]}.session"
                )
            ),
            self.config.data[CONF_API_ID],
            self.config.data[CONF_API_HASH],
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][config.entry_id] = self

        @self.client.on(events.NewMessage)
        async def new_message_handler(event: events.newmessage.NewMessage.Event):
            hass.bus.async_fire(
                "telegram_client_new_message",
                {
                    key: getattr(event.message, key)
                    for key in (
                        "message",
                        "raw_text",
                        "sender_id",
                        "chat_id",
                        "is_channel",
                        "is_group",
                        "is_private",
                        "silent",
                        "post",
                        "from_scheduled",
                        "date",
                    )
                    if hasattr(event.message, key)
                },
            )

    @property
    def client(self) -> TelegramClient:
        """Telegram client."""
        return self._client

    @property
    def config(self) -> ConfigEntry:
        """Telegram client config entry."""
        return self._config
