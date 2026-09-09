"""Support for the imap services."""

import asyncio
from email.message import Message
import logging
from typing import Any

from aioimaplib import IMAP4_SSL, AioImapException, Response
import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import ImapMessage, connect_to_server, get_parts
from .errors import InvalidAuth, InvalidFolder

_LOGGER = logging.getLogger(__name__)

CONF_ENTRY = "entry"
CONF_SEEN = "seen"
CONF_PART = "part"
CONF_UID = "uid"
CONF_TARGET_FOLDER = "target_folder"

_SERVICE_UID_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ENTRY): cv.string,
        vol.Required(CONF_UID): cv.string,
    }
)

SERVICE_SEEN_SCHEMA = _SERVICE_UID_SCHEMA
SERVICE_MOVE_SCHEMA = _SERVICE_UID_SCHEMA.extend(
    {
        vol.Optional(CONF_SEEN): cv.boolean,
        vol.Required(CONF_TARGET_FOLDER): cv.string,
    }
)
SERVICE_DELETE_SCHEMA = _SERVICE_UID_SCHEMA
SERVICE_FETCH_TEXT_SCHEMA = _SERVICE_UID_SCHEMA
SERVICE_FETCH_PART_SCHEMA = _SERVICE_UID_SCHEMA.extend(
    {
        vol.Required(CONF_PART): cv.string,
    }
)


async def async_get_imap_client(hass: HomeAssistant, entry_id: str) -> IMAP4_SSL:
    """Get IMAP client and connect."""
    if (entry := hass.config_entries.async_get_entry(entry_id)) is None or (
        entry.state is not ConfigEntryState.LOADED
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entry",
        )
    try:
        client = await connect_to_server(entry.data)
    except InvalidAuth as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_auth"
        ) from exc
    except InvalidFolder as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_folder"
        ) from exc
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    return client


@callback
def raise_on_error(response: Response, translation_key: str) -> None:
    """Get error message from response."""
    if response.result != "OK":
        error: str = response.lines[0].decode("utf-8")
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={"error": error},
        )


@callback
def _get_message_part(message: Message, part_key: str) -> Message:
    part: Message | Any = message
    for index in part_key.split(","):
        sub_parts = part.get_payload()
        try:
            assert isinstance(sub_parts, list)
            part = sub_parts[int(index)]
        except (AssertionError, ValueError, IndexError) as exc:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_part_index",
            ) from exc

    return part


async def _async_seen(call: ServiceCall) -> None:
    """Process mark as seen service call."""
    entry_id: str = call.data[CONF_ENTRY]
    uid: str = call.data[CONF_UID]
    _LOGGER.debug(
        "Mark message %s as seen. Entry: %s",
        uid,
        entry_id,
    )
    client = await async_get_imap_client(call.hass, entry_id)
    try:
        response = await client.store(uid, "+FLAGS (\\Seen)")
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    raise_on_error(response, "seen_failed")
    await client.close()


async def _async_move(call: ServiceCall) -> None:
    """Process move email service call."""
    entry_id: str = call.data[CONF_ENTRY]
    uid: str = call.data[CONF_UID]
    seen = bool(call.data.get(CONF_SEEN))
    target_folder: str = call.data[CONF_TARGET_FOLDER]
    _LOGGER.debug(
        "Move message %s to folder %s. Mark as seen: %s. Entry: %s",
        uid,
        target_folder,
        seen,
        entry_id,
    )
    client = await async_get_imap_client(call.hass, entry_id)
    try:
        if seen:
            response = await client.store(uid, "+FLAGS (\\Seen)")
            raise_on_error(response, "seen_failed")
        response = await client.copy(uid, target_folder)
        raise_on_error(response, "copy_failed")
        response = await client.store(uid, "+FLAGS (\\Deleted)")
        raise_on_error(response, "delete_failed")
        response = await asyncio.wait_for(
            client.protocol.expunge(uid, by_uid=True), client.timeout
        )
        raise_on_error(response, "expunge_failed")
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    await client.close()


async def _async_delete(call: ServiceCall) -> None:
    """Process deleting email service call."""
    entry_id: str = call.data[CONF_ENTRY]
    uid: str = call.data[CONF_UID]
    _LOGGER.debug(
        "Delete message %s. Entry: %s",
        uid,
        entry_id,
    )
    client = await async_get_imap_client(call.hass, entry_id)
    try:
        response = await client.store(uid, "+FLAGS (\\Deleted)")
        raise_on_error(response, "delete_failed")
        response = await asyncio.wait_for(
            client.protocol.expunge(uid, by_uid=True), client.timeout
        )
        raise_on_error(response, "expunge_failed")
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    await client.close()


async def _async_fetch(call: ServiceCall) -> ServiceResponse:
    """Process fetch email service and return content."""
    entry_id: str = call.data[CONF_ENTRY]
    uid: str = call.data[CONF_UID]
    _LOGGER.debug(
        "Fetch text for message %s. Entry: %s",
        uid,
        entry_id,
    )
    client = await async_get_imap_client(call.hass, entry_id)
    try:
        response = await client.fetch(uid, "BODY.PEEK[]")
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    raise_on_error(response, "fetch_failed")
    # Index 1 of of the response lines contains the bytearray with the message data
    message = ImapMessage(response.lines[1])
    await client.close()
    return {
        "text": message.text,
        "sender": message.sender,
        "subject": message.subject,
        "parts": get_parts(message.email_message),
        "uid": uid,
    }


async def _async_fetch_part(call: ServiceCall) -> ServiceResponse:
    """Process fetch email part service and return content."""
    entry_id: str = call.data[CONF_ENTRY]
    uid: str = call.data[CONF_UID]
    part_key: str = call.data[CONF_PART]
    _LOGGER.debug(
        "Fetch part %s for message %s. Entry: %s",
        part_key,
        uid,
        entry_id,
    )
    client = await async_get_imap_client(call.hass, entry_id)
    try:
        response = await client.fetch(uid, "BODY.PEEK[]")
    except (TimeoutError, AioImapException) as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="imap_server_fail",
            translation_placeholders={"error": str(exc)},
        ) from exc
    raise_on_error(response, "fetch_failed")
    # Index 1 of of the response lines contains the bytearray with the message data
    message = ImapMessage(response.lines[1])
    await client.close()
    part_data = _get_message_part(message.email_message, part_key)
    part_data_content = part_data.get_payload(decode=False)
    try:
        assert isinstance(part_data_content, str)
    except AssertionError as exc:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_part_index",
        ) from exc
    return {
        "part_data": part_data_content,
        "content_type": part_data.get_content_type(),
        "content_transfer_encoding": part_data.get("Content-Transfer-Encoding"),
        "filename": part_data.get_filename(),
        "part": part_key,
        "uid": uid,
    }


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the imap services."""
    hass.services.async_register(DOMAIN, "seen", _async_seen, SERVICE_SEEN_SCHEMA)
    hass.services.async_register(DOMAIN, "move", _async_move, SERVICE_MOVE_SCHEMA)
    hass.services.async_register(DOMAIN, "delete", _async_delete, SERVICE_DELETE_SCHEMA)
    hass.services.async_register(
        DOMAIN,
        "fetch",
        _async_fetch,
        SERVICE_FETCH_TEXT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "fetch_part",
        _async_fetch_part,
        SERVICE_FETCH_PART_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
