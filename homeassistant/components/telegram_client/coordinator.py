"""Telegram client data update coordinator."""

from asyncio import timeout
from collections.abc import Coroutine
from datetime import timedelta
from pathlib import Path
from typing import Any

from telethon import TelegramClient, __version__ as sw_version, events
from telethon.errors.common import AuthKeyNotFound
from telethon.errors.rpcbaseerrors import AuthKeyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_API_HASH,
    CONF_API_ID,
    CONF_PHONE,
    CONF_SESSION_ID,
    DOMAIN,
    LOGGER,
    UPDATE_INTERVAL,
)

type TelegramClientEntryConfigEntry = ConfigEntry[TelegramClientCoordinator]


class TelegramClientCoordinator(DataUpdateCoordinator):
    """Telegram client coordinator."""

    _unique_id: str | None
    _phone: str
    _client: TelegramClient

    def __init__(
        self, hass: HomeAssistant, entry: TelegramClientEntryConfigEntry
    ) -> None:
        """Initialize Telegram client coordinator."""
        self._unique_id = entry.unique_id
        self._phone = entry.data[CONF_PHONE]
        name = f"Telegram client ({self._phone})"
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
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **self._device_info
        )
        self._client = TelegramClient(
            Path(
                hass.config.path(
                    STORAGE_DIR, DOMAIN, f"{entry.data[CONF_SESSION_ID]}.session"
                )
            ),
            entry.data[CONF_API_ID],
            entry.data[CONF_API_HASH],
        )
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = self

        @self._client.on(events.NewMessage)
        async def on_new_message(event: events.newmessage.NewMessage.Event):
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

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        me = await self.async_client_call(self._client.get_me())
        return {
            "me": {
                "user_id": me.id,
                "username": me.username,
                "restricted": me.restricted,
                "premium": me.premium,
                "last_name": me.last_name,
                "first_name": me.first_name,
                "phone": me.phone,
            }
        }

    async def async_client_call[_T](self, coro: Coroutine[Any, Any, _T]) -> _T:
        """Call a coro or raise exception."""
        try:
            async with timeout(10):
                return await coro
        except (AuthKeyError, AuthKeyNotFound) as ex:
            raise ConfigEntryAuthFailed(
                f"Credentials expired for {self._phone}"
            ) from ex

    async def async_client_start(self):
        """Start the client."""
        await self.async_client_call(self._client.start())

    async def async_client_disconnect(self):
        """Disconnect the client."""
        await self.async_client_call(self._client.disconnect())
