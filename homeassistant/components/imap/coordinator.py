"""Coordinator for imag integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import email
import logging
from typing import Any

from aioimaplib import AUTH, IMAP4_SSL, NONAUTH, SELECTED, AioImapException
import async_timeout

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONTENT_TYPE_TEXT_PLAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import SSLCipherList, client_context

from .const import (
    CONF_CHARSET,
    CONF_FOLDER,
    CONF_SEARCH,
    CONF_SERVER,
    CONF_SSL_CIPHER_LIST,
    DOMAIN,
)
from .errors import InvalidAuth, InvalidFolder

_LOGGER = logging.getLogger(__name__)

BACKOFF_TIME = 10

EVENT_IMAP = "imap_content"


async def connect_to_server(data: Mapping[str, Any]) -> IMAP4_SSL:
    """Connect to imap server and return client."""
    ssl_context = client_context(
        ssl_cipher_list=data.get(CONF_SSL_CIPHER_LIST, SSLCipherList.PYTHON_DEFAULT)
    )
    client = IMAP4_SSL(data[CONF_SERVER], data[CONF_PORT], ssl_context=ssl_context)

    await client.wait_hello_from_server()

    if client.protocol.state == NONAUTH:
        await client.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    if client.protocol.state not in {AUTH, SELECTED}:
        raise InvalidAuth("Invalid username or password")
    if client.protocol.state == AUTH:
        await client.select(data[CONF_FOLDER])
    if client.protocol.state != SELECTED:
        raise InvalidFolder(f"Folder {data[CONF_FOLDER]} is invalid")
    return client


class ImapMessage:
    """Class to parse an RFC822 email message."""

    def __init__(self, raw_message: bytes) -> None:
        """Initialize IMAP message."""
        self.email_message = email.message_from_bytes(raw_message)

    @property
    def headers(self) -> dict[str, tuple[str,]]:
        """Get the email headers."""
        header_base: dict[str, tuple[str,]] = {}
        for key, value in self.email_message.items():
            header: tuple[str,] = (str(value),)
            if header_base.setdefault(key, header) != header:
                header_base[key] += header  # type: ignore[assignment]
        return header_base

    @property
    def date(self) -> datetime | None:
        """Get the date the email was sent."""
        # See https://www.rfc-editor.org/rfc/rfc2822#section-3.3
        date_str: str | None
        if (date_str := self.email_message["Date"]) is None:
            return None
        # In some cases a timezone or comment is added in parenthesis after the date
        # We want to strip that part to avoid parsing errors
        return datetime.strptime(
            date_str.split("(")[0].strip(), "%a, %d %b %Y %H:%M:%S %z"
        )

    @property
    def sender(self) -> str:
        """Get the parsed message sender from the email."""
        return str(email.utils.parseaddr(self.email_message["From"])[1])

    @property
    def subject(self) -> str:
        """Decode the message subject."""
        decoded_header = email.header.decode_header(self.email_message["Subject"])
        header = email.header.make_header(decoded_header)
        return str(header)

    @property
    def text(self) -> str:
        """Get the message text from the email.

        Will look for text/plain or use text/html if not found.
        """
        message_text = None
        message_html = None
        message_untyped_text = None

        for part in self.email_message.walk():
            if part.get_content_type() == CONTENT_TYPE_TEXT_PLAIN:
                if message_text is None:
                    message_text = part.get_payload()
            elif part.get_content_type() == "text/html":
                if message_html is None:
                    message_html = part.get_payload()
            elif (
                part.get_content_type().startswith("text")
                and message_untyped_text is None
            ):
                message_untyped_text = part.get_payload()

        if message_text is not None:
            return message_text

        if message_html is not None:
            return message_html

        if message_untyped_text is not None:
            return message_untyped_text

        return self.email_message.get_payload()


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
        self._last_message_id: str | None = None
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

    async def _async_process_event(self, last_message_id: str) -> None:
        """Send a event for the last message if the last message was changed."""
        response = await self.imap_client.fetch(last_message_id, "BODY.PEEK[]")
        if response.result == "OK":
            message = ImapMessage(response.lines[1])
            data = {
                "server": self.config_entry.data[CONF_SERVER],
                "username": self.config_entry.data[CONF_USERNAME],
                "search": self.config_entry.data[CONF_SEARCH],
                "folder": self.config_entry.data[CONF_FOLDER],
                "date": message.date,
                "text": message.text[:2048],
                "sender": message.sender,
                "subject": message.subject,
                "headers": message.headers,
            }
            self.hass.bus.fire(EVENT_IMAP, data)
            _LOGGER.debug(
                "Message processed, sender: %s, subject: %s",
                message.sender,
                message.subject,
            )

    async def _async_fetch_number_of_messages(self) -> int | None:
        """Fetch last message and messages count."""
        await self._async_reconnect_if_needed()
        await self.imap_client.noop()
        result, lines = await self.imap_client.search(
            self.config_entry.data[CONF_SEARCH],
            charset=self.config_entry.data[CONF_CHARSET],
        )
        if result != "OK":
            raise UpdateFailed(
                f"Invalid response for search '{self.config_entry.data[CONF_SEARCH]}': {result} / {lines[0]}"
            )
        count: int = len(message_ids := lines[0].split())
        last_message_id = (
            str(message_ids[-1:][0], encoding=self.config_entry.data[CONF_CHARSET])
            if count
            else None
        )
        if (
            count
            and last_message_id is not None
            and self._last_message_id != last_message_id
        ):
            self._last_message_id = last_message_id
            await self._async_process_event(last_message_id)

        return count

    async def _cleanup(self, log_error: bool = False) -> None:
        """Close resources."""
        if self.imap_client:
            try:
                if self.imap_client.has_pending_idle():
                    self.imap_client.idle_done()
                await self.imap_client.stop_wait_server_push()
                await self.imap_client.close()
                await self.imap_client.logout()
            except (AioImapException, asyncio.TimeoutError):
                if log_error:
                    _LOGGER.debug("Error while cleaning up imap connection")
            self.imap_client = None

    async def shutdown(self, *_) -> None:
        """Close resources."""
        await self._cleanup(log_error=True)


class ImapPollingDataUpdateCoordinator(ImapDataUpdateCoordinator):
    """Class for imap client."""

    def __init__(self, hass: HomeAssistant, imap_client: IMAP4_SSL) -> None:
        """Initiate imap client."""
        super().__init__(hass, imap_client, timedelta(seconds=10))

    async def _async_update_data(self) -> int | None:
        """Update the number of unread emails."""
        try:
            return await self._async_fetch_number_of_messages()
        except (
            AioImapException,
            UpdateFailed,
            asyncio.TimeoutError,
        ) as ex:
            await self._cleanup()
            self.async_set_update_error(ex)
            raise UpdateFailed() from ex
        except InvalidFolder as ex:
            _LOGGER.warning("Selected mailbox folder is invalid")
            await self._cleanup()
            self.async_set_update_error(ex)
            raise ConfigEntryError("Selected mailbox folder is invalid.") from ex
        except InvalidAuth as ex:
            _LOGGER.warning("Username or password incorrect, starting reauthentication")
            await self._cleanup()
            self.async_set_update_error(ex)
            raise ConfigEntryAuthFailed() from ex


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
            try:
                number_of_messages = await self._async_fetch_number_of_messages()
            except InvalidAuth as ex:
                await self._cleanup()
                _LOGGER.warning(
                    "Username or password incorrect, starting reauthentication"
                )
                self.config_entry.async_start_reauth(self.hass)
                self.async_set_update_error(ex)
                await asyncio.sleep(BACKOFF_TIME)
            except InvalidFolder as ex:
                _LOGGER.warning("Selected mailbox folder is invalid")
                await self._cleanup()
                self.config_entry.async_set_state(
                    self.hass,
                    ConfigEntryState.SETUP_ERROR,
                    "Selected mailbox folder is invalid.",
                )
                self.async_set_update_error(ex)
                await asyncio.sleep(BACKOFF_TIME)
            except (
                UpdateFailed,
                AioImapException,
                asyncio.TimeoutError,
            ) as ex:
                await self._cleanup()
                self.async_set_update_error(ex)
                await asyncio.sleep(BACKOFF_TIME)
                continue
            else:
                self.async_set_updated_data(number_of_messages)
            try:
                idle: asyncio.Future = await self.imap_client.idle_start()
                await self.imap_client.wait_server_push()
                self.imap_client.idle_done()
                async with async_timeout.timeout(10):
                    await idle

            except (AioImapException, asyncio.TimeoutError):
                _LOGGER.debug(
                    "Lost %s (will attempt to reconnect after %s s)",
                    self.config_entry.data[CONF_SERVER],
                    BACKOFF_TIME,
                )
                await self._cleanup()
                await asyncio.sleep(BACKOFF_TIME)

    async def shutdown(self, *_) -> None:
        """Close resources."""
        if self._push_wait_task:
            self._push_wait_task.cancel()
        await super().shutdown()
