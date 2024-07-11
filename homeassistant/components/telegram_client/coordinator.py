"""Telegram client data update coordinator."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
import re
import sqlite3
from typing import Any

from telethon import TelegramClient, __version__ as sw_version, events, tl
from telethon.errors import AccessTokenExpiredError, AccessTokenInvalidError
from telethon.errors.common import AuthKeyNotFound
from telethon.errors.rpcbaseerrors import AuthKeyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
)
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CLIENT_TYPE_CLIENT,
    CONF_API_HASH,
    CONF_API_ID,
    CONF_CLIENT_TYPE,
    CONF_PHONE,
    CONF_TOKEN,
    DOMAIN,
    EVENT_CALLBACK_QUERY,
    EVENT_CHAT_ACTION,
    EVENT_INLINE_QUERY,
    EVENT_MESSAGE_DELETED,
    EVENT_MESSAGE_EDITED,
    EVENT_MESSAGE_READ,
    EVENT_NEW_MESSAGE,
    EVENT_USER_UPDATE,
    KEY_ACTION,
    KEY_ACTION_MESSAGE,
    KEY_ADDED_BY,
    KEY_AUDIO,
    KEY_CANCEL,
    KEY_CHAT,
    KEY_CHAT_ID,
    KEY_CHAT_INSTANCE,
    KEY_CLIENT,
    KEY_CONTACT,
    KEY_CONTENTS,
    KEY_CREATED,
    KEY_DATA,
    KEY_DATA_MATCH,
    KEY_DELETED_ID,
    KEY_DELETED_IDS,
    KEY_DOCUMENT,
    KEY_GEO,
    KEY_ID,
    KEY_INBOX,
    KEY_INPUT_CHAT,
    KEY_INPUT_SENDER,
    KEY_INPUT_USER,
    KEY_INPUT_USERS,
    KEY_IS_CHANNEL,
    KEY_IS_GROUP,
    KEY_IS_PRIVATE,
    KEY_KICKED_BY,
    KEY_LAST_SEEN,
    KEY_MAX_ID,
    KEY_MESSAGE,
    KEY_MESSAGE_ID,
    KEY_MESSAGE_IDS,
    KEY_NEW_PHOTO,
    KEY_NEW_PIN,
    KEY_NEW_SCORE,
    KEY_NEW_TITLE,
    KEY_OFFSET,
    KEY_ONLINE,
    KEY_OUTBOX,
    KEY_PATTERN_MATCH,
    KEY_PHOTO,
    KEY_PLAYING,
    KEY_QUERY,
    KEY_RECENTLY,
    KEY_RECORDING,
    KEY_ROUND,
    KEY_SENDER,
    KEY_SENDER_ID,
    KEY_STATUS,
    KEY_STICKER,
    KEY_TYPING,
    KEY_UNPIN,
    KEY_UNTIL,
    KEY_UPLOADING,
    KEY_USER,
    KEY_USER_ADDED,
    KEY_USER_ID,
    KEY_USER_IDS,
    KEY_USER_JOINED,
    KEY_USER_KICKED,
    KEY_USER_LEFT,
    KEY_USERS,
    KEY_VIA_INLINE,
    KEY_VIDEO,
    KEY_WITHIN_MONTHS,
    KEY_WITHIN_WEEKS,
    LOGGER,
    OPTION_BLACKLIST_CHATS,
    OPTION_BLACKLIST_USERS,
    OPTION_CHATS,
    OPTION_DATA,
    OPTION_EVENTS,
    OPTION_FORWARDS,
    OPTION_FROM_USERS,
    OPTION_INBOX,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    OPTION_PATTERN,
    OPTION_USERS,
    SCAN_INTERVAL,
    SENSOR_FIRST_NAME,
    SENSOR_LAST_NAME,
    SENSOR_PHONE,
    SENSOR_PREMIUM,
    SENSOR_RESTRICTED,
    SENSOR_USER_ID,
    SENSOR_USERNAME,
)

type TelegramClientEntryConfigEntry = ConfigEntry[TelegramClientCoordinator]


class TelegramClientCoordinator(DataUpdateCoordinator):
    """Telegram client coordinator."""

    _unique_id: str | None
    _entry: TelegramClientEntryConfigEntry
    _hass: HomeAssistant
    _client: TelegramClient
    _last_sent_message_id_sensor: Any
    _last_edited_message_id_sensor: Any
    _last_deleted_message_id_sensor: Any

    def __init__(
        self, hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
    ) -> None:
        """Initialize Telegram client coordinator."""
        self._unique_id = entry.unique_id
        self._entry = entry
        self._hass = hass
        name = f"Telegram {entry.data.get(CONF_CLIENT_TYPE)} ({entry.unique_id})"
        self._hass = hass
        name = f"Telegram {entry.data.get(CONF_CLIENT_TYPE)} ({entry.unique_id})"
        self._device_info = {
            "identifiers": {(DOMAIN, entry.unique_id)},
            "name": name,
            "manufacturer": "Telethon",
            "sw_version": sw_version,
        }
        super().__init__(
            hass,
            LOGGER,
            name=name,
            update_interval=SCAN_INTERVAL,
        )
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **self._device_info
        )
        session_id = (
            re.sub(r"\D", "", self._entry.data[CONF_PHONE])
            if self._entry.data.get(CONF_CLIENT_TYPE) == CLIENT_TYPE_CLIENT
            else self._entry.data.get(CONF_TOKEN, "").split(":")[0]
        )
        self._client = TelegramClient(
            Path(hass.config.path(STORAGE_DIR, DOMAIN, f"{session_id}.session")),
            entry.data.get(CONF_API_ID),
            entry.data.get(CONF_API_HASH),
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = self
        self._subscribe_listeners(entry)

    @property
    def device_info(self):
        """Device info."""
        return self._device_info

    @property
    def unique_id(self):
        """Unique id."""
        return self._unique_id

    @property
    def client(self):
        """Client."""
        return self._client

    @property
    def last_sent_message_id(self) -> Any:
        """Last sent message id."""
        return self._last_sent_message_id

    @last_sent_message_id.setter
    def last_sent_message_id(self, sensor: Any):
        self._last_sent_message_id = sensor

    @property
    def last_edited_message_id(self) -> Any:
        """Last edited message id."""
        return self._last_edited_message_id_sensor

    @last_edited_message_id.setter
    def last_edited_message_id(self, sensor: Any):
        self._last_edited_message_id_sensor = sensor

    @property
    def last_deleted_message_id(self) -> Any:
        """Last deleted message id."""
        return self._last_deleted_message_id_sensor

    @last_deleted_message_id.setter
    def last_deleted_message_id(self, sensor: Any):
        self._last_deleted_message_id_sensor = sensor

    @callback
    async def on_new_message(self, event: events.newmessage.NewMessage.Event):
        """Process new message event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_NEW_MESSAGE}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_INPUT_CHAT,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_MESSAGE,
                    KEY_PATTERN_MATCH,
                ],
            ),
        )

    @callback
    async def on_message_edited(self, event: events.messageedited.MessageEdited.Event):
        """Process message edited event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_EDITED}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_INPUT_CHAT,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_MESSAGE,
                    KEY_PATTERN_MATCH,
                ],
            ),
        )

    @callback
    async def on_message_read(self, event: events.messageread.MessageRead.Event):
        """Process message read event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_READ}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_CONTENTS,
                    KEY_INBOX,
                    KEY_INPUT_CHAT,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_MAX_ID,
                    KEY_MESSAGE_IDS,
                    KEY_OUTBOX,
                ],
            ),
        )

    @callback
    async def on_message_deleted(
        self, event: events.messagedeleted.MessageDeleted.Event
    ):
        """Process message deleted event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_DELETED}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_DELETED_ID,
                    KEY_DELETED_IDS,
                    KEY_INPUT_CHAT,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                ],
            ),
        )

    @callback
    async def on_callback_query(self, event: events.callbackquery.CallbackQuery.Event):
        """Process callback query event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_CALLBACK_QUERY}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_CHAT_INSTANCE,
                    KEY_DATA,
                    KEY_DATA_MATCH,
                    KEY_ID,
                    KEY_INPUT_CHAT,
                    KEY_INPUT_SENDER,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_MESSAGE_ID,
                    KEY_PATTERN_MATCH,
                    KEY_QUERY,
                    KEY_SENDER,
                    KEY_SENDER_ID,
                    KEY_VIA_INLINE,
                ],
            ),
        )

    @callback
    async def on_inline_query(self, event: events.inlinequery.InlineQuery.Event):
        """Process inline query event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_INLINE_QUERY}",
            self._data_to_dict(
                event,
                [
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_GEO,
                    KEY_ID,
                    KEY_INPUT_CHAT,
                    KEY_INPUT_SENDER,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_OFFSET,
                    KEY_PATTERN_MATCH,
                ],
            ),
        )

    @callback
    async def on_chat_action(self, event: events.chataction.ChatAction.Event):
        """Process chat action event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_CHAT_ACTION}",
            self._data_to_dict(
                event,
                [
                    KEY_ACTION_MESSAGE,
                    KEY_ADDED_BY,
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_CREATED,
                    KEY_INPUT_CHAT,
                    KEY_INPUT_USER,
                    KEY_INPUT_USERS,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_KICKED_BY,
                    KEY_NEW_PHOTO,
                    KEY_NEW_PIN,
                    KEY_NEW_SCORE,
                    KEY_NEW_TITLE,
                    KEY_PHOTO,
                    KEY_UNPIN,
                    KEY_USER,
                    KEY_USERS,
                    KEY_USER_ADDED,
                    KEY_USER_ID,
                    KEY_USER_IDS,
                    KEY_USER_JOINED,
                    KEY_USER_KICKED,
                    KEY_USER_LEFT,
                ],
            ),
        )

    @callback
    async def on_user_update(self, event: events.userupdate.UserUpdate.Event):
        """Process message deleted event."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_USER_UPDATE}",
            self._data_to_dict(
                event,
                [
                    KEY_ACTION,
                    KEY_AUDIO,
                    KEY_CANCEL,
                    KEY_CHAT,
                    KEY_CHAT_ID,
                    KEY_CONTACT,
                    KEY_DOCUMENT,
                    KEY_GEO,
                    KEY_INPUT_CHAT,
                    KEY_INPUT_SENDER,
                    KEY_INPUT_USER,
                    KEY_IS_CHANNEL,
                    KEY_IS_GROUP,
                    KEY_IS_PRIVATE,
                    KEY_LAST_SEEN,
                    KEY_ONLINE,
                    KEY_PHOTO,
                    KEY_PLAYING,
                    KEY_RECENTLY,
                    KEY_RECORDING,
                    KEY_ROUND,
                    KEY_SENDER,
                    KEY_SENDER_ID,
                    KEY_STATUS,
                    KEY_STICKER,
                    KEY_TYPING,
                    KEY_UNTIL,
                    KEY_UPLOADING,
                    KEY_USER,
                    KEY_USER_ID,
                    KEY_VIDEO,
                    KEY_WITHIN_MONTHS,
                    KEY_WITHIN_WEEKS,
                ],
            ),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        me = await self.async_client_call(self._client.get_me())
        return self._data_to_dict(
            me,
            [
                SENSOR_USER_ID,
                SENSOR_USERNAME,
                SENSOR_RESTRICTED,
                SENSOR_PREMIUM,
                SENSOR_LAST_NAME,
                SENSOR_FIRST_NAME,
                SENSOR_PHONE,
            ],
        )

    async def async_client_call[_T](self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Call a coro or raise exception."""
        try:
            await self.async_client_start()
            if not await self._client.is_user_authorized():
                raise ConfigEntryAuthFailed(
                    f"User is not authorized for {self._unique_id}"
                )
            async with asyncio.timeout(10):
                result = await coro
                if result is None:
                    raise ConfigEntryNotReady(
                        f"API call returned None for {self._unique_id}"
                    )
                return result
        except (
            AuthKeyError,
            AuthKeyNotFound,
            ConfigEntryAuthFailed,
        ) as err:
            await self._client.log_out()
            raise ConfigEntryAuthFailed(err) from err
        except sqlite3.OperationalError as err:
            raise ConfigEntryAuthFailed(err) from err
        except ConnectionError as err:
            retries = 3
            for i in range(retries):
                await asyncio.sleep(1)
                LOGGER.warning(f"API call raised an error {err} for {i + 1} time(s)")
                try:
                    return await coro
                finally:
                    pass
            raise IntegrationError(f"API call failed {retries} times.") from err

    async def async_client_start(self):
        """Start the client."""
        if not self._client.is_connected():
            try:
                if self._entry.data[CONF_CLIENT_TYPE] == CLIENT_TYPE_CLIENT:
                    await self._client.connect()
                    if not await self._client.is_user_authorized():
                        raise ConfigEntryAuthFailed("Credentials has expired")
                    await self._client.start(phone=self._entry.data[CONF_PHONE])
                else:
                    await self._client.start(bot_token=self._entry.data[CONF_TOKEN])
            except (
                AccessTokenExpiredError,
                AccessTokenInvalidError,
                ConnectionError,
                ConfigEntryAuthFailed,
            ) as err:
                await self._client.log_out()
                raise ConfigEntryAuthFailed(err) from err

    async def async_client_disconnect(self, retries=5, delay=1):
        """Disconnect the client."""
        if self._client.is_connected():
            await self._client.disconnect()

    def _subscribe_listeners(self, entry: ConfigEntry) -> None:
        """Subscribe listeners."""
        events_config = entry.options.get(OPTION_EVENTS, {})
        if events_config.get(EVENT_NEW_MESSAGE):
            options = entry.options.get(EVENT_NEW_MESSAGE, {})
            self._client.add_event_handler(
                self.on_new_message,
                events.NewMessage(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                    incoming=options.get(OPTION_INCOMING),
                    outgoing=options.get(OPTION_OUTGOING),
                    from_users=cv.ensure_list_csv(options.get(OPTION_FROM_USERS))
                    or None,
                    forwards=options.get(OPTION_FORWARDS),
                    pattern=options.get(OPTION_PATTERN),
                ),
            )
        if events_config.get(EVENT_MESSAGE_EDITED):
            options = entry.options.get(EVENT_MESSAGE_EDITED, {})
            self._client.add_event_handler(
                self.on_message_edited,
                events.MessageEdited(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                    incoming=options.get(OPTION_INCOMING),
                    outgoing=options.get(OPTION_OUTGOING),
                    from_users=cv.ensure_list_csv(options.get(OPTION_FROM_USERS))
                    or None,
                    forwards=options.get(OPTION_FORWARDS),
                    pattern=options.get(OPTION_PATTERN),
                ),
            )
        if events_config.get(EVENT_MESSAGE_READ):
            options = entry.options.get(EVENT_MESSAGE_READ, {})
            self._client.add_event_handler(
                self.on_message_read,
                events.MessageRead(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                    inbox=options.get(OPTION_INBOX),
                ),
            )
        if events_config.get(EVENT_MESSAGE_DELETED):
            options = entry.options.get(EVENT_MESSAGE_DELETED, {})
            self._client.add_event_handler(
                self.on_message_deleted,
                events.MessageDeleted(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                ),
            )
        if events_config.get(EVENT_CALLBACK_QUERY):
            options = entry.options.get(EVENT_CALLBACK_QUERY, {})
            self._client.add_event_handler(
                self.on_callback_query,
                events.CallbackQuery(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                    data=options.get(OPTION_DATA),
                    pattern=options.get(OPTION_PATTERN),
                ),
            )
        if events_config.get(EVENT_INLINE_QUERY):
            options = entry.options.get(EVENT_INLINE_QUERY, {})
            self._client.add_event_handler(
                self.on_inline_query,
                events.InlineQuery(
                    users=list(map(int, cv.ensure_list_csv(options.get(OPTION_USERS))))
                    or None,
                    blacklist_users=options.get(OPTION_BLACKLIST_USERS),
                    pattern=options.get(OPTION_PATTERN),
                ),
            )
        if events_config.get(EVENT_CHAT_ACTION):
            options = entry.options.get(EVENT_CHAT_ACTION, {})
            self._client.add_event_handler(
                self.on_chat_action,
                events.ChatAction(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                ),
            )
        if events_config.get(EVENT_USER_UPDATE):
            options = entry.options.get(EVENT_USER_UPDATE, {})
            self._client.add_event_handler(
                self.on_user_update,
                events.UserUpdate(
                    chats=list(map(int, cv.ensure_list_csv(options.get(OPTION_CHATS))))
                    or None,
                    blacklist_chats=options.get(OPTION_BLACKLIST_CHATS),
                ),
            )

    def _unsubscribe_listeners(self, entry: ConfigEntry) -> None:
        """Unsubscribe listeners."""
        self._client.remove_event_handler(self.on_new_message, events.NewMessage)
        self._client.remove_event_handler(self.on_message_edited, events.MessageEdited)
        self._client.remove_event_handler(self.on_message_read, events.MessageRead)
        self._client.remove_event_handler(
            self.on_message_deleted, events.MessageDeleted
        )
        self._client.remove_event_handler(self.on_callback_query, events.CallbackQuery)
        self._client.remove_event_handler(self.on_inline_query, events.InlineQuery)
        self._client.remove_event_handler(self.on_chat_action, events.ChatAction)
        self._client.remove_event_handler(self.on_user_update, events.UserUpdate)

    async def resubscribe_listeners(
        self, hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
    ):
        """Resubscribe listeners."""
        self._unsubscribe_listeners(entry)
        self._subscribe_listeners(entry)

    def _tlobject_to_dict(self, data):
        if isinstance(data, list):
            return list(map(self._tlobject_to_dict, data))
        if isinstance(data, re.Match):
            return data.groupdict()
        if isinstance(data, tl.TLObject):
            return data.to_dict()
        return data

    def _data_to_dict(self, event, keys):
        return dict(
            {
                key: self._tlobject_to_dict(getattr(event, key))
                for key in keys
                if hasattr(event, key)
            },
            **{KEY_CLIENT: self.data},
        )
