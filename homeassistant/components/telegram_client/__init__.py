"""The Telegram client integration."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from telethon.errors.common import AuthKeyNotFound
from telethon.errors.rpcbaseerrors import AuthKeyError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import CONF_PHONE, DOMAIN
from .device import TelegramClientDevice

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


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


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
        device_entity = device_registry.async_get(device_id)
        if not device_entity:
            return
        device: TelegramClientDevice = hass.data[DOMAIN].get(
            device_entity.primary_config_entry
        )

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
                await device.client.send_message(
                    target,
                    message,
                    reply_to=reply_to,
                    parse_mode=parse_mode,
                    link_preview=link_preview,
                    silent=silent,
                    schedule=schedule,
                )
        except (AuthKeyError, AuthKeyNotFound) as ex:
            await device.client.log_out()
            raise ConfigEntryAuthFailed(
                f"Credentials expired for {device.entry.data[CONF_PHONE]}"
            ) from ex

    hass.services.async_register(
        DOMAIN, SERVICE_SEND_MESSAGE, async_telegram_call, schema=SEND_MESSAGE_SCHEMA
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle Telegram client entry setup."""
    device = TelegramClientDevice(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await device.async_start()

    return device.is_connected


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if entry.entry_id in hass.data[DOMAIN]:
        device = hass.data[DOMAIN][entry.entry_id]
        await device.async_disconnect()
        del hass.data[DOMAIN][entry.entry_id]
        return not device.is_connected

    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    await async_unload_entry(hass, entry)
