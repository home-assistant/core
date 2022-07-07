"""The imap integration."""
from __future__ import annotations

from asyncio import Task, TimeoutError as AsyncIOTimeoutError
from datetime import timedelta
import logging

from aioimaplib import IMAP4_SSL, AioImapException
import async_timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_CHARSET, CONF_FOLDER, CONF_SEARCH, CONF_SERVER, DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def connect_to_server(
    server: str, port: int, username: str, password: str, folder: str
) -> IMAP4_SSL:
    """Connect to imap server and return client."""
    client = IMAP4_SSL(server, port)
    await client.wait_hello_from_server()
    await client.login(username, password)
    await client.select(folder)
    return client


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up imap from a config entry."""
    try:
        imap_client: IMAP4_SSL = await connect_to_server(
            entry.data[CONF_SERVER],
            entry.data[CONF_PORT],
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_FOLDER],
        )
    except AioImapException as err:
        raise ConfigEntryAuthFailed from err
    except AsyncIOTimeoutError as err:
        raise ConfigEntryNotReady from err

    coordinator = ImapDataUpdateCoordinator(hass, entry, imap_client)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.support_push:
        coordinator.idle_loop_task = hass.loop.create_task(coordinator.idle_loop())
    else:
        coordinator.update_interval = timedelta(seconds=10)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, coordinator.shutdown)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class ImapDataUpdateCoordinator(DataUpdateCoordinator[int]):
    """Class for imap client."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, imap_client: IMAP4_SSL
    ) -> None:
        """Initiate imap client."""
        self.hass = hass
        self.entry: ConfigEntry = entry
        self.imap_client = imap_client
        self.idle_loop_task: Task | None = None
        self.support_push = imap_client.has_capability("IDLE")
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )

    async def _async_update_data(self) -> int:
        """Update the number of unread emails."""
        try:
            if self.imap_client is None:
                await self.retry_connection()
        except (AioImapException, AsyncIOTimeoutError) as err:
            raise UpdateFailed(err) from err

        return await self.refresh_email_count()

    async def refresh_email_count(self) -> int:
        """Check the number of found emails."""
        await self.imap_client.noop()
        result, lines = await self.imap_client.search(
            self.entry.data[CONF_SEARCH], charset=self.entry.data[CONF_CHARSET]
        )

        if result != "OK":
            raise UpdateFailed(
                f"Invalid response for search '{self.entry.data[CONF_SEARCH]}': {result} / {lines[0]}"
            )
        return len(lines[0].split())

    async def idle_loop(self) -> None:
        """Wait for data pushed from server."""
        while True:
            try:
                idle = await self.imap_client.idle_start()
                await self.imap_client.wait_server_push()
                self.imap_client.idle_done()
                async with async_timeout.timeout(10):
                    await idle
                await self.async_request_refresh()
            except (AioImapException, AsyncIOTimeoutError):
                _LOGGER.warning(
                    "Lost %s (will attempt to reconnect)", self.entry.data[CONF_SERVER]
                )
                self.imap_client = None
                await self.async_request_refresh()

    async def retry_connection(self):
        """Retry the connection in case of error."""
        self.imap_client = await connect_to_server(
            self.entry.data[CONF_SERVER],
            self.entry.data[CONF_PORT],
            self.entry.data[CONF_USERNAME],
            self.entry.data[CONF_PASSWORD],
            self.entry.data[CONF_FOLDER],
        )
        if self.support_push:
            self.hass.loop.create_task(self.idle_loop())

    async def shutdown(self, *_) -> None:
        """Close resources."""
        if self.imap_client:
            if self.imap_client.has_pending_idle():
                self.imap_client.idle_done()
            await self.imap_client.logout()
        if self.idle_loop_task:
            self.idle_loop_task.cancel()
