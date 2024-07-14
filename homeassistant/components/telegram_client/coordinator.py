"""Telegram client data update coordinator."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
import re
import sqlite3
from typing import Any

from telethon import Button, TelegramClient, __version__ as sw_version, events, tl
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
    CLIENT_PARAMS,
    CLIENT_TYPE_USER,
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
    FIELD_BUTTONS,
    FIELD_FILE,
    FIELD_INLINE_KEYBOARD,
    FIELD_KEYBOARD,
    FIELD_KEYBOARD_RESIZE,
    FIELD_TARGET_ID,
    FIELD_TARGET_USERNAME,
    KEY_ACTION,
    KEY_ACTION_MESSAGE,
    KEY_ADDED_BY,
    KEY_AUDIO,
    KEY_CANCEL,
    KEY_CHAT,
    KEY_CHAT_ID,
    KEY_CHAT_INSTANCE,
    KEY_CONFIG_ENTRY_ID,
    KEY_CONTACT,
    KEY_CONTENTS,
    KEY_CREATED,
    KEY_DATA,
    KEY_DATA_MATCH,
    KEY_DELETED_ID,
    KEY_DELETED_IDS,
    KEY_DOCUMENT,
    KEY_ENTITY,
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
    KEY_ME,
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
    SENSOR_ID,
    SENSOR_LAST_NAME,
    SENSOR_PHONE,
    SENSOR_PREMIUM,
    SENSOR_RESTRICTED,
    SENSOR_USERNAME,
)

type TelegramClientEntryConfigEntry = ConfigEntry[TelegramClientCoordinator]


class TelegramClientCoordinator(DataUpdateCoordinator):
    """Telegram client data update coordinator."""

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
        """Handle Telegram client data update coordinator initialization."""
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
            if self._entry.data.get(CONF_CLIENT_TYPE) == CLIENT_TYPE_USER
            else self._entry.data.get(CONF_TOKEN, "").split(":")[0]
        )
        self._client = TelegramClient(
            Path(hass.config.path(STORAGE_DIR, DOMAIN, f"{session_id}.session")),
            entry.data.get(CONF_API_ID),
            entry.data.get(CONF_API_HASH),
            **CLIENT_PARAMS,
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = self
        self._subscribe_listeners(entry)

    @property
    def device_info(self):
        """Get device info."""
        return self._device_info

    @property
    def unique_id(self):
        """Get unique ID."""
        return self._unique_id

    @property
    def client(self):
        """Get Telegram client instance."""
        return self._client

    @property
    def last_sent_message_id(self) -> Any:
        """Get Last sent message ID sensor."""
        return self._last_sent_message_id

    @last_sent_message_id.setter
    def last_sent_message_id(self, sensor: Any):
        """Set Last sent message ID sensor."""
        self._last_sent_message_id = sensor

    @property
    def last_edited_message_id(self) -> Any:
        """Get Last edited message ID sensor."""
        return self._last_edited_message_id_sensor

    @last_edited_message_id.setter
    def last_edited_message_id(self, sensor: Any):
        """Set Last edited message ID sensor."""
        self._last_edited_message_id_sensor = sensor

    @property
    def last_deleted_message_id(self) -> Any:
        """Get Last deleted message ID sensor."""
        return self._last_deleted_message_id_sensor

    @last_deleted_message_id.setter
    def last_deleted_message_id(self, sensor: Any):
        """Set Last deleted message ID sensor."""
        self._last_deleted_message_id_sensor = sensor

    @callback
    async def on_new_message(self, event: events.newmessage.NewMessage.Event):
        """Handle new message event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_NEW_MESSAGE}",
            self._event_to_dict(
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
        """Handle message edited event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_EDITED}",
            self._event_to_dict(
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
        """Handle message read event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_READ}",
            self._event_to_dict(
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
        """Handle message deleted event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_MESSAGE_DELETED}",
            self._event_to_dict(
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
        """Handle callback query event propagation."""
        data = self._event_to_dict(
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
        )
        if bdata := data.get(KEY_DATA):
            data[KEY_DATA] = bdata.decode("UTF-8")
        if bdata := data.get(KEY_QUERY, {}).get(KEY_DATA):
            data[KEY_QUERY][KEY_DATA] = bdata.decode("UTF-8")
        self._hass.bus.async_fire(f"{DOMAIN}_{EVENT_CALLBACK_QUERY}", data)

    @callback
    async def on_inline_query(self, event: events.inlinequery.InlineQuery.Event):
        """Handle inline query event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_INLINE_QUERY}",
            self._event_to_dict(
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
        """Handle chat action event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_CHAT_ACTION}",
            self._event_to_dict(
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
        """Handle user update event propagation."""
        self._hass.bus.async_fire(
            f"{DOMAIN}_{EVENT_USER_UPDATE}",
            self._event_to_dict(
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

    async def send_messages(self, data):
        """Handle Send messages service call."""
        self._process_data(data)
        target_usernames = data.pop(FIELD_TARGET_USERNAME, [])
        target_ids = data.pop(FIELD_TARGET_ID, [])
        for target in target_usernames + target_ids:
            data[KEY_ENTITY] = target
            message = await self.client.send_message(**data)
        self.last_sent_message_id.set_state(message.id)

    async def edit_message(self, data):
        """Handle Edit message service call."""
        self._process_data(data)
        target_username = data.pop(FIELD_TARGET_USERNAME, None)
        target_id = data.pop(FIELD_TARGET_ID, None)
        data[KEY_ENTITY] = target_username or target_id
        message = await self.client.edit_message(**data)
        self.last_edited_message_id.set_state(message.id)

    async def delete_messages(self, data):
        """Handle Delete messages service call."""
        self._process_data(data)
        target_usernames = data.pop(FIELD_TARGET_USERNAME, [])
        target_ids = data.pop(FIELD_TARGET_ID, [])
        data[KEY_ENTITY] = target_usernames + target_ids
        await self.client.delete_messages(**data)
        message_ids = cv.ensure_list(data.get(KEY_MESSAGE_ID))
        self.last_deleted_message_id.set_state(message_ids[-1])

    def _process_data(self, data):
        """Handle Send messages and Edit message services data processing."""

        def inline_button(data):
            """Handle inline button generation."""
            return (
                Button.inline(data)
                if isinstance(data, str)
                else Button.inline(data.get("text"), data.get("data"))
            )

        if keyboard := data.pop(FIELD_KEYBOARD, None):
            if not isinstance(keyboard[0], list):
                keyboard = [keyboard]
            data[FIELD_BUTTONS] = [
                [
                    Button.text(
                        button,
                        resize=data.pop(FIELD_KEYBOARD_RESIZE, None),
                        single_use=data.pop(FIELD_KEYBOARD, None),
                    )
                    for button in row
                ]
                for row in keyboard
            ]
        if inline_keyboard := data.pop(FIELD_INLINE_KEYBOARD, None):
            if not isinstance(inline_keyboard[0], list):
                inline_keyboard = [inline_keyboard]
            data[FIELD_BUTTONS] = [
                [inline_button(button) for button in row] for row in inline_keyboard
            ]
        if file := data.get(FIELD_FILE):
            data[FIELD_FILE] = list(map(self.hass.config.path, file))

    async def _async_update_data(self):
        """Handle sensors data update."""
        me = await self._async_client_call(self._client.get_me())
        return {
            key: getattr(me, key)
            for key in (
                SENSOR_ID,
                SENSOR_USERNAME,
                SENSOR_RESTRICTED,
                SENSOR_PREMIUM,
                SENSOR_LAST_NAME,
                SENSOR_FIRST_NAME,
                SENSOR_PHONE,
            )
        }

    async def _async_client_call[_T](self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Handle safe Telegram client call."""
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
            raise IntegrationError("API call failed") from err

    async def async_client_start(self):
        """Handle Telegram client start."""
        if not self._client.is_connected():
            try:
                if self._entry.data[CONF_CLIENT_TYPE] == CLIENT_TYPE_USER:
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
        """Handle Telegram client stop."""
        if self._client.is_connected():
            await self._client.disconnect()

    def _subscribe_listeners(self, entry: ConfigEntry) -> None:
        """Handle Telegram client events listeners subscription."""
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
        """Handle Telegram client events listeners unsubscription."""
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
        """Handle Telegram client events listeners re-subscription."""
        self._unsubscribe_listeners(entry)
        self._subscribe_listeners(entry)

    def _tlobject_to_dict(self, data):
        """Handle Telegram client objects to dict conversion."""

        def cleanup_data(data: Any) -> Any:
            """Handle byte strings and "_" keys deletion."""
            if isinstance(data, list):
                return [cleanup_data(value) for value in data]
            if isinstance(data, dict):
                return {
                    key: cleanup_data(value)
                    for key, value in data.items()
                    if key != "_" and not isinstance(value, bytes)
                }
            return data

        if isinstance(data, list):
            return list(map(self._tlobject_to_dict, data))
        if isinstance(data, re.Match):
            return data.groupdict()
        if isinstance(data, tl.TLObject):
            return cleanup_data(data.to_dict())
        return data

    def _event_to_dict(self, event, keys):
        """Handle Telegram client data to dict conversion."""
        return dict(
            {
                key: self._tlobject_to_dict(getattr(event, key))
                for key in keys
                if hasattr(event, key)
            },
            **{KEY_CONFIG_ENTRY_ID: self._entry.entry_id, KEY_ME: self.data},
        )
