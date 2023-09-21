"""Coordinator for imag integration."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta
import email
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
import logging
from typing import Any

from aioimaplib import AUTH, IMAP4_SSL, NONAUTH, SELECTED, AioImapException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_TEXT_PLAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    TemplateError,
)
from homeassistant.helpers.json import json_bytes
from homeassistant.helpers.template import Template
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import (
    SSLCipherList,
    client_context,
    create_no_verify_ssl_context,
)

from .const import (
    CONF_CHARSET,
    CONF_CUSTOM_EVENT_DATA_TEMPLATE,
    CONF_FOLDER,
    CONF_MAX_MESSAGE_SIZE,
    CONF_SEARCH,
    CONF_SERVER,
    CONF_SSL_CIPHER_LIST,
    DEFAULT_MAX_MESSAGE_SIZE,
    DOMAIN,
)
from .errors import InvalidAuth, InvalidFolder

_LOGGER = logging.getLogger(__name__)

BACKOFF_TIME = 10

EVENT_IMAP = "imap_content"
MAX_ERRORS = 3
MAX_EVENT_DATA_BYTES = 32168


async def connect_to_server(data: Mapping[str, Any]) -> IMAP4_SSL:
    """Connect to imap server and return client."""
    ssl_cipher_list: str = data.get(CONF_SSL_CIPHER_LIST, SSLCipherList.PYTHON_DEFAULT)
    if data.get(CONF_VERIFY_SSL, True):
        ssl_context = client_context(ssl_cipher_list=ssl_cipher_list)
    else:
        ssl_context = create_no_verify_ssl_context()
    client = IMAP4_SSL(data[CONF_SERVER], data[CONF_PORT], ssl_context=ssl_context)
    _LOGGER.debug(
        "Wait for hello message from server %s on port %s, verify_ssl: %s",
        data[CONF_SERVER],
        data[CONF_PORT],
        data.get(CONF_VERIFY_SSL, True),
    )
    await client.wait_hello_from_server()
    if client.protocol.state == NONAUTH:
        _LOGGER.debug(
            "Authenticating with %s on server %s",
            data[CONF_USERNAME],
            data[CONF_SERVER],
        )
        await client.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    if client.protocol.state not in {AUTH, SELECTED}:
        raise InvalidAuth("Invalid username or password")
    if client.protocol.state == AUTH:
        _LOGGER.debug(
            "Selecting mail folder %s on server %s",
            data[CONF_FOLDER],
            data[CONF_SERVER],
        )
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
            header_instances: tuple[str,] = (str(value),)
            if header_base.setdefault(key, header_instances) != header_instances:
                header_base[key] += header_instances  # type: ignore[assignment]
        return header_base

    @property
    def message_id(self) -> str | None:
        """Get the message ID."""
        value: str
        for header, value in self.email_message.items():
            if header == "Message-ID":
                return value
        return None

    @property
    def date(self) -> datetime | None:
        """Get the date the email was sent."""
        # See https://www.rfc-editor.org/rfc/rfc2822#section-3.3
        date_str: str | None
        if (date_str := self.email_message["Date"]) is None:
            return None
        try:
            mail_dt_tm = parsedate_to_datetime(date_str)
        except ValueError:
            _LOGGER.debug(
                "Parsed date %s is not compliant with rfc2822#section-3.3", date_str
            )
            return None
        return mail_dt_tm

    @property
    def sender(self) -> str:
        """Get the parsed message sender from the email."""
        return str(parseaddr(self.email_message["From"])[1])

    @property
    def subject(self) -> str:
        """Decode the message subject."""
        decoded_header = decode_header(self.email_message["Subject"] or "")
        subject_header = make_header(decoded_header)
        return str(subject_header)

    @property
    def text(self) -> str:
        """Get the message text from the email.

        Will look for text/plain or use text/html if not found.
        """
        message_text: str | None = None
        message_html: str | None = None
        message_untyped_text: str | None = None

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

        return str(self.email_message.get_payload())


class ImapDataUpdateCoordinator(DataUpdateCoordinator[int | None]):
    """Base class for imap client."""

    config_entry: ConfigEntry
    custom_event_template: Template | None

    def __init__(
        self,
        hass: HomeAssistant,
        imap_client: IMAP4_SSL,
        entry: ConfigEntry,
        update_interval: timedelta | None,
    ) -> None:
        """Initiate imap client."""
        self.imap_client = imap_client
        self.auth_errors: int = 0
        self._last_message_uid: str | None = None
        self._last_message_id: str | None = None
        self.custom_event_template = None
        _custom_event_template = entry.data.get(CONF_CUSTOM_EVENT_DATA_TEMPLATE)
        if _custom_event_template is not None:
            self.custom_event_template = Template(_custom_event_template, hass=hass)
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

    async def _async_process_event(self, last_message_uid: str) -> None:
        """Send a event for the last message if the last message was changed."""
        response = await self.imap_client.fetch(last_message_uid, "BODY.PEEK[]")
        if response.result == "OK":
            message = ImapMessage(response.lines[1])
            # Set `initial` to `False` if the last message is triggered again
            initial: bool = True
            if (message_id := message.message_id) == self._last_message_id:
                initial = False
            self._last_message_id = message_id
            data = {
                "server": self.config_entry.data[CONF_SERVER],
                "username": self.config_entry.data[CONF_USERNAME],
                "search": self.config_entry.data[CONF_SEARCH],
                "folder": self.config_entry.data[CONF_FOLDER],
                "initial": initial,
                "date": message.date,
                "text": message.text,
                "sender": message.sender,
                "subject": message.subject,
                "headers": message.headers,
            }
            if self.custom_event_template is not None:
                try:
                    data["custom"] = self.custom_event_template.async_render(
                        data, parse_result=True
                    )
                    _LOGGER.debug(
                        "IMAP custom template (%s) for msguid %s (%s) rendered to: %s, initial: %s",
                        self.custom_event_template,
                        last_message_uid,
                        message_id,
                        data["custom"],
                        initial,
                    )
                except TemplateError as err:
                    data["custom"] = None
                    _LOGGER.error(
                        "Error rendering IMAP custom template (%s) for msguid %s "
                        "failed with message: %s",
                        self.custom_event_template,
                        last_message_uid,
                        err,
                    )
            data["text"] = message.text[
                : self.config_entry.data.get(
                    CONF_MAX_MESSAGE_SIZE, DEFAULT_MAX_MESSAGE_SIZE
                )
            ]
            if (size := len(json_bytes(data))) > MAX_EVENT_DATA_BYTES:
                _LOGGER.warning(
                    "Custom imap_content event skipped, size (%s) exceeds "
                    "the maximal event size (%s), sender: %s, subject: %s",
                    size,
                    MAX_EVENT_DATA_BYTES,
                    message.sender,
                    message.subject,
                )
                return

            self.hass.bus.fire(EVENT_IMAP, data)
            _LOGGER.debug(
                "Message with id %s (%s) processed, sender: %s, subject: %s, initial: %s",
                last_message_uid,
                message_id,
                message.sender,
                message.subject,
                initial,
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
        if not (count := len(message_ids := lines[0].split())):
            self._last_message_uid = None
            return 0
        last_message_uid = (
            str(message_ids[-1:][0], encoding=self.config_entry.data[CONF_CHARSET])
            if count
            else None
        )
        if (
            count
            and last_message_uid is not None
            and self._last_message_uid != last_message_uid
        ):
            self._last_message_uid = last_message_uid
            await self._async_process_event(last_message_uid)

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
            finally:
                self.imap_client = None

    async def shutdown(self, *_: Any) -> None:
        """Close resources."""
        await self._cleanup(log_error=True)


class ImapPollingDataUpdateCoordinator(ImapDataUpdateCoordinator):
    """Class for imap client."""

    def __init__(
        self, hass: HomeAssistant, imap_client: IMAP4_SSL, entry: ConfigEntry
    ) -> None:
        """Initiate imap client."""
        _LOGGER.debug(
            "Connected to server %s using IMAP polling", entry.data[CONF_SERVER]
        )
        super().__init__(hass, imap_client, entry, timedelta(seconds=10))

    async def _async_update_data(self) -> int | None:
        """Update the number of unread emails."""
        try:
            messages = await self._async_fetch_number_of_messages()
            self.auth_errors = 0
            return messages
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
            await self._cleanup()
            self.auth_errors += 1
            if self.auth_errors <= MAX_ERRORS:
                _LOGGER.warning("Authentication failed, retrying")
            else:
                _LOGGER.warning(
                    "Username or password incorrect, starting reauthentication"
                )
                self.config_entry.async_start_reauth(self.hass)
            self.async_set_update_error(ex)
            raise ConfigEntryAuthFailed() from ex


class ImapPushDataUpdateCoordinator(ImapDataUpdateCoordinator):
    """Class for imap client."""

    def __init__(
        self, hass: HomeAssistant, imap_client: IMAP4_SSL, entry: ConfigEntry
    ) -> None:
        """Initiate imap client."""
        _LOGGER.debug("Connected to server %s using IMAP push", entry.data[CONF_SERVER])
        super().__init__(hass, imap_client, entry, None)
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
                self.auth_errors += 1
                await self._cleanup()
                if self.auth_errors <= MAX_ERRORS:
                    _LOGGER.warning("Authentication failed, retrying")
                else:
                    _LOGGER.warning(
                        "Username or password incorrect, starting reauthentication"
                    )
                    self.config_entry.async_start_reauth(self.hass)
                self.async_set_update_error(ex)
                await asyncio.sleep(BACKOFF_TIME)
            except InvalidFolder as ex:
                _LOGGER.warning("Selected mailbox folder is invalid")
                await self._cleanup()
                self.async_set_update_error(ex)
                await asyncio.sleep(BACKOFF_TIME)
                continue
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
                self.auth_errors = 0
                self.async_set_updated_data(number_of_messages)
            try:
                idle: asyncio.Future = await self.imap_client.idle_start()
                await self.imap_client.wait_server_push()
                self.imap_client.idle_done()
                async with asyncio.timeout(10):
                    await idle

            # From python 3.11 asyncio.TimeoutError is an alias of TimeoutError
            except (AioImapException, asyncio.TimeoutError):
                _LOGGER.debug(
                    "Lost %s (will attempt to reconnect after %s s)",
                    self.config_entry.data[CONF_SERVER],
                    BACKOFF_TIME,
                )
                await self._cleanup()
                await asyncio.sleep(BACKOFF_TIME)

    async def shutdown(self, *_: Any) -> None:
        """Close resources."""
        if self._push_wait_task:
            self._push_wait_task.cancel()
        await super().shutdown()
