"""Telegram client device class."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from telethon import TelegramClient, __version__ as sw_version, events
from telethon.errors.common import AuthKeyNotFound
from telethon.errors.rpcbaseerrors import AuthKeyError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import STORAGE_DIR

from .const import CONF_API_HASH, CONF_API_ID, CONF_PHONE, CONF_SESSION_ID, DOMAIN


class TelegramClientDevice:
    """Telegram client device class."""

    _hass: HomeAssistant
    _entry: ConfigEntry
    _client: TelegramClient
    _binary_sensors: list[Any] = []
    _sensors: list[Any] = []
    _data: dict = {}
    _unsub_polling: CALLBACK_TYPE

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Init."""
        self._hass = hass
        self._entry = entry
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id, **self.device_info
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
    def hass(self) -> HomeAssistant:
        """Home Assistant instance."""
        return self._hass

    @property
    def entry(self) -> ConfigEntry:
        """Config entry instance."""
        return self._entry

    @property
    def client(self) -> TelegramClient:
        """Telegram client instance."""
        return self._client

    @property
    def binary_sensors(self) -> list[Any]:
        """Binary sensors."""
        return self._binary_sensors

    @property
    def sensors(self) -> list[Any]:
        """Sensors."""
        return self._sensors

    @property
    def data(self) -> dict[str, Any]:
        """Device data."""
        return self._data

    @property
    def device_info(self):
        """Device information."""
        return {
            "identifiers": {(DOMAIN, self.entry.unique_id)},
            "name": f"Telegram client ({self.entry.data[CONF_PHONE]})",
            "manufacturer": "Telethon",
            "sw_version": sw_version,
        }

    @property
    def is_connected(self):
        """Is telegram client connected."""
        return self._client.is_connected()

    async def async_disconnect(self):
        """Disconnect."""
        self._client.disconnect()

    async def async_start(self, restart=False):
        """Start device."""
        if restart:
            self.stop_polling()
            await self._client.disconnect()
        try:
            await self._client.connect()
            if await self._client.is_user_authorized():
                await self._client.start(self._entry.data[CONF_PHONE])
            else:
                raise AuthKeyNotFound
        except (AuthKeyError, AuthKeyNotFound) as ex:
            await self._client.log_out()
            raise ConfigEntryAuthFailed(
                f"Credentials expired for {self._entry.data[CONF_PHONE]}"
            ) from ex
        await self.async_start_polling()

    async def async_start_polling(self):
        """Start polling."""
        self._unsub_polling = async_track_time_interval(
            self.hass, self.async_update_data, timedelta(seconds=5)
        )
        await self.async_update_data()

    def stop_polling(self):
        """Stop polling."""
        if self._unsub_polling:
            self._unsub_polling()
            self._unsub_polling = None

    async def async_validate_auth(self):
        """Validate auth."""
        try:
            await self._client.connect()
            if await self._client.is_user_authorized():
                await self._client.start(self._entry.data[CONF_PHONE])
            else:
                raise AuthKeyNotFound
        except (AuthKeyError, AuthKeyNotFound) as ex:
            await self._client.log_out()
            raise ConfigEntryAuthFailed(
                f"Credentials expired for {self._entry.data[CONF_PHONE]}"
            ) from ex

    async def async_update_me_data(self):
        """Update `me` data."""
        me = self.data["me"] = await self.client.get_me()
        if me is None:
            await self.async_start(restart=True)

    async def async_update_data(self, now=None):
        """Update device data."""
        await self.async_update_me_data()
        for binary_sensor in self.binary_sensors:
            binary_sensor.update_state()
        for sensor in self.sensors:
            sensor.update_state()
