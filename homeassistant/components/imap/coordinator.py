"""Coordinator for imag integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import timedelta
import logging
from typing import Any

from aioimaplib import AUTH, IMAP4_SSL, SELECTED, AioImapException
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHARSET, CONF_FOLDER, CONF_SEARCH, CONF_SERVER, DOMAIN
from .errors import InvalidAuth, InvalidFolder

_LOGGER = logging.getLogger(__name__)

BACKOFF_TIME = 10


async def connect_to_server(data: Mapping[str, Any]) -> IMAP4_SSL:
    """Connect to imap server and return client."""
    client = IMAP4_SSL(data[CONF_SERVER], data[CONF_PORT])
    await client.wait_hello_from_server()
    await client.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    if client.protocol.state != AUTH:
        raise InvalidAuth
    await client.select(data[CONF_FOLDER])
    if client.protocol.state != SELECTED:
        raise InvalidFolder
    return client


class ImapDataUpdateCoordinator(DataUpdateCoordinator[int | None]):
    """Base class for imap client."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        imap_client: IMAP4_SSL,
        update_interval: timedelta | None,
    ) -> None:
        """Initiate imap client."""
        self.imap_client = imap_client
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )

    async def async_start(self) -> None:
        """Start coordinator."""

    async def _async_reconnect_if_needed(self) -> None:
        """Connect to imap server."""
        if self.imap_client is None:
            self.imap_client = await connect_to_server(self.config_entry.data)

    async def _async_fetch_number_of_messages(self) -> int:
        """Fetch number of messages."""
        try:
            await self._async_reconnect_if_needed()
            await self.imap_client.noop()
            result, lines = await self.imap_client.search(
                self.config_entry.data[CONF_SEARCH],
                charset=self.config_entry.data[CONF_CHARSET],
            )
        except (AioImapException, asyncio.TimeoutError) as err:
            await self._cleanup()
            raise UpdateFailed(err) from err

        if result != "OK":
            raise UpdateFailed(
                f"Invalid response for search '{self.config_entry.data[CONF_SEARCH]}': {result} / {lines[0]}"
            )
        return len(lines[0].split())

    async def _cleanup(self) -> None:
        """Close resources."""
        if self.imap_client:
            try:
                if self.imap_client.has_pending_idle():
                    self.imap_client.idle_done()
                await self.imap_client.stop_wait_server_push()
                await self.imap_client.logout()
                await self.imap_client.close()
            except AioImapException:
                _LOGGER.warning("Error while cleaning up imap connection")
            self.imap_client = None

    async def shutdown(self, *_) -> None:
        """Close resources."""
        await self._cleanup()


class ImapPollingDataUpdateCoordinator(ImapDataUpdateCoordinator):
    """Class for imap client."""

    def __init__(self, hass: HomeAssistant, imap_client: IMAP4_SSL) -> None:
        """Initiate imap client."""
        super().__init__(hass, imap_client, timedelta(seconds=10))

    async def _async_update_data(self) -> int | None:
        """Update the number of unread emails."""
        return await self._async_fetch_number_of_messages()


class ImapPushDataUpdateCoordinator(ImapDataUpdateCoordinator):
    """Class for imap client."""

    def __init__(self, hass: HomeAssistant, imap_client: IMAP4_SSL) -> None:
        """Initiate imap client."""
        super().__init__(hass, imap_client, None)
        self._push_wait_task: asyncio.Task[None] | None = None

    async def _async_update_data(self) -> int | None:
        """Update the number of unread emails."""
        await self.async_start()
        return None

    async def async_start(self) -> None:
        """Start coordinator."""
        self._push_wait_task = self.hass.async_create_background_task(
            self._async_wait_push_loop(), "Wait for IMAP data push"
        )

    async def _async_wait_push_loop(self) -> None:
        """Wait for data push from server."""
        while True:
            await self._async_reconnect_if_needed()
            try:
                number_of_messages = await self._async_fetch_number_of_messages()
            except UpdateFailed as ex:
                self.async_set_update_error(ex)
            else:
                self.async_set_updated_data(number_of_messages)
            try:
                idle: asyncio.Future = await self.imap_client.idle_start()
                await self.imap_client.wait_server_push()
                self.imap_client.idle_done()
                async with async_timeout.timeout(10):
                    await idle

            except (AioImapException, asyncio.TimeoutError):
                _LOGGER.warning(
                    "Lost %s (will attempt to reconnect)",
                    self.config_entry.data[CONF_SERVER],
                )
                self.async_set_update_error(UpdateFailed("Lost connection"))
                await self._cleanup()
                await asyncio.sleep(BACKOFF_TIME)
                continue

    async def shutdown(self, *_) -> None:
        """Close resources."""
        if self._push_wait_task:
            self._push_wait_task.cancel()
        await super().shutdown()
