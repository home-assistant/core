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


class ImapDataUpdateCoordinator(DataUpdateCoordinator[int]):
    """Class for imap client."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, imap_client: IMAP4_SSL) -> None:
        """Initiate imap client."""
        self.hass = hass
        self.imap_client = imap_client
        self.support_push = imap_client.has_capability("IDLE")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=10) if not self.support_push else None,
        )

    async def _async_update_data(self) -> int:
        """Update the number of unread emails."""
        try:
            if self.imap_client is None:
                self.imap_client = await connect_to_server(self.config_entry.data)
        except (AioImapException, asyncio.TimeoutError) as err:
            raise UpdateFailed(err) from err

        return await self.refresh_email_count()

    async def refresh_email_count(self) -> int:
        """Check the number of found emails."""
        try:
            await self.imap_client.noop()
            result, lines = await self.imap_client.search(
                self.config_entry.data[CONF_SEARCH],
                charset=self.config_entry.data[CONF_CHARSET],
            )
        except (AioImapException, asyncio.TimeoutError) as err:
            raise UpdateFailed(err) from err

        if result != "OK":
            raise UpdateFailed(
                f"Invalid response for search '{self.config_entry.data[CONF_SEARCH]}': {result} / {lines[0]}"
            )
        if self.support_push:
            self.hass.async_create_task(self.async_wait_server_push())
        return len(lines[0].split())

    async def async_wait_server_push(self) -> None:
        """Wait for data push from server."""
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
            self.imap_client = None
        await self.async_request_refresh()

    async def shutdown(self, *_) -> None:
        """Close resources."""
        if self.imap_client:
            await self.imap_client.stop_wait_server_push()
            await self.imap_client.logout()
