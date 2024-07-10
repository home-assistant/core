"""Telegram client data update coordinator."""

import asyncio
from collections.abc import Coroutine
from pathlib import Path
import re
import sqlite3
from typing import Any

from telethon import TelegramClient, __version__ as sw_version, events
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
    EVENT_NEW_MESSAGE,
    LOGGER,
    OPTION_BLACKLIST_CHATS,
    OPTION_CHATS,
    OPTION_EVENTS,
    OPTION_FORWARDS,
    OPTION_FROM_USERS,
    OPTION_INCOMING,
    OPTION_OUTGOING,
    OPTION_PATTERN,
    SCAN_INTERVAL,
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

    def __init__(
        self, hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
    ) -> None:
        """Initialize Telegram client coordinator."""
        self._unique_id = entry.unique_id
        self._entry = entry
        self._hass = hass
        name = f"Telegram {entry.data[CONF_CLIENT_TYPE]} ({entry.unique_id})"
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
            if self._entry.data[CONF_CLIENT_TYPE] == CLIENT_TYPE_CLIENT
            else self._entry.data[CONF_TOKEN].split(":")[0]
        )
        self._client = TelegramClient(
            Path(hass.config.path(STORAGE_DIR, DOMAIN, f"{session_id}.session")),
            entry.data[CONF_API_ID],
            entry.data[CONF_API_HASH],
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

    @callback
    async def on_new_message(self, event: events.newmessage.NewMessage.Event):
        """Process new message event."""
        data = {
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
        }
        data["client"] = self.data
        self._hass.bus.async_fire(f"{DOMAIN}_{EVENT_NEW_MESSAGE}", data)

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        me = await self.async_client_call(self._client.get_me())
        return {
            "user_id": me.id,
            "username": me.username,
            "restricted": me.restricted,
            "premium": me.premium,
            "last_name": me.last_name,
            "first_name": me.first_name,
            "phone": me.phone,
        }

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
            new_message_options = entry.options.get(EVENT_NEW_MESSAGE, {})
            self._client.add_event_handler(
                self.on_new_message,
                events.NewMessage(
                    chats=list(
                        map(
                            int,
                            cv.ensure_list_csv(new_message_options.get(OPTION_CHATS)),
                        )
                    )
                    or None,
                    blacklist_chats=new_message_options.get(OPTION_BLACKLIST_CHATS),
                    incoming=new_message_options.get(OPTION_INCOMING),
                    outgoing=new_message_options.get(OPTION_OUTGOING),
                    from_users=cv.ensure_list_csv(
                        new_message_options.get(OPTION_FROM_USERS)
                    )
                    or None,
                    forwards=new_message_options.get(OPTION_FORWARDS),
                    pattern=new_message_options.get(OPTION_PATTERN),
                ),
            )

    def _unsubscribe_listeners(self, entry: ConfigEntry) -> None:
        """Unsubscribe listeners."""
        self._client.remove_event_handler(self.on_new_message, events.NewMessage)

    async def resubscribe_listeners(
        self, hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
    ):
        """Resubscribe listeners."""
        self._unsubscribe_listeners(entry)
        self._subscribe_listeners(entry)
