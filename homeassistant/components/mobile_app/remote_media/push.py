"""Send one Remote Now Playing update through the Home Assistant push relay.

Deliberately not `notify._send_message`: that collapses every relay failure into a generic
`HomeAssistantError`, and this caller has to tell a dead session token — the one condition that
removes a registration — from a relay configuration fault, which must not.

The relay owns everything about APNs; Core never sends a topic, a host, or provider configuration.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from ..const import (
    ATTR_APP_DATA,
    ATTR_APP_ID,
    ATTR_APP_VERSION,
    ATTR_OS_VERSION,
    ATTR_PUSH_TOKEN,
    ATTR_PUSH_URL,
    ATTR_WEBHOOK_ID,
)
from .const import (
    ATTR_ATTRIBUTES,
    ATTR_EVENT,
    ATTR_NOW_PLAYING,
    ATTR_NOW_PLAYING_TOKEN,
    ATTR_REGISTRATION_INFO,
    ATTR_TIMESTAMP,
    ERROR_APNS_RATE_LIMITED,
    ERROR_APNS_UNAVAILABLE,
    ERROR_INVALID_TOKEN,
    ERROR_NOT_CONFIGURED,
    ERROR_PAYLOAD_TOO_LARGE,
    ERROR_PROVIDER_AUTH,
    ERROR_RATE_LIMITED,
    ERROR_TOPIC_MISMATCH,
    ERROR_UNSUPPORTED_APP,
)

_LOGGER = logging.getLogger(__name__)

RELAY_TIMEOUT_SECONDS = 15


class PushOutcome(Enum):
    """What Core should do about a relay result.

    Only `REMOVE` means the user's session token is dead. A topic mismatch, a credential fault or a
    deployment that does not serve this build are all problems on our side of the wire, and deleting
    a registration over one would silently stop a feature the user never turned off.
    """

    DELIVERED = "delivered"
    # The session token will never work again. This is the only outcome that unregisters.
    REMOVE = "remove"
    # Transient. Try again when something meaningful next changes.
    RETRY = "retry"
    # Told to slow down. Stay quiet for a while.
    BACK_OFF = "back_off"
    # A configuration or programming fault that will not resolve on its own. Keep the
    # registration, complain once, and stop sending for a long while.
    MISCONFIGURED = "misconfigured"


# Relay `errorType` to outcome. Anything unrecognised is treated as retryable rather than as a
# reason to delete a registration, because a relay that grows a new error must not cost users
# their sessions.
_OUTCOMES: dict[str, PushOutcome] = {
    ERROR_INVALID_TOKEN: PushOutcome.REMOVE,
    ERROR_UNSUPPORTED_APP: PushOutcome.MISCONFIGURED,
    ERROR_TOPIC_MISMATCH: PushOutcome.MISCONFIGURED,
    ERROR_PROVIDER_AUTH: PushOutcome.MISCONFIGURED,
    ERROR_NOT_CONFIGURED: PushOutcome.MISCONFIGURED,
    ERROR_PAYLOAD_TOO_LARGE: PushOutcome.MISCONFIGURED,
    ERROR_RATE_LIMITED: PushOutcome.BACK_OFF,
    ERROR_APNS_RATE_LIMITED: PushOutcome.BACK_OFF,
    ERROR_APNS_UNAVAILABLE: PushOutcome.RETRY,
    # Request-shape refusals. Core built the request, so these are our bug, not the token's.
    "AmbiguousRequest": PushOutcome.MISCONFIGURED,
    "InvalidNowPlayingToken": PushOutcome.MISCONFIGURED,
    "InvalidNowPlayingRequest": PushOutcome.MISCONFIGURED,
    "UnsupportedNowPlayingEvent": PushOutcome.MISCONFIGURED,
    "InvalidNowPlayingTimestamp": PushOutcome.MISCONFIGURED,
    "InvalidNowPlayingAttributes": PushOutcome.MISCONFIGURED,
    "MissingNowPlayingSessionId": PushOutcome.MISCONFIGURED,
}


@dataclass(frozen=True, slots=True)
class PushResult:
    """The relay's answer, reduced to what the caller acts on."""

    outcome: PushOutcome
    error_type: str | None = None
    status: int | None = None


def build_request(
    entry: ConfigEntry,
    now_playing_token: str,
    event: str,
    timestamp: int,
    attributes: dict[str, Any],
) -> dict[str, Any]:
    """Return the relay request body.

    `push_token` stays the ordinary Companion token, which is the registration and rate-limit
    identity; `now_playing_token` is only the destination.
    """
    app_data = entry.data[ATTR_APP_DATA]
    registration_info = {
        ATTR_APP_ID: entry.data[ATTR_APP_ID],
        ATTR_APP_VERSION: entry.data[ATTR_APP_VERSION],
        ATTR_WEBHOOK_ID: entry.data[ATTR_WEBHOOK_ID],
    }
    if ATTR_OS_VERSION in entry.data:
        registration_info[ATTR_OS_VERSION] = entry.data[ATTR_OS_VERSION]

    return {
        ATTR_PUSH_TOKEN: app_data[ATTR_PUSH_TOKEN],
        ATTR_NOW_PLAYING_TOKEN: now_playing_token,
        ATTR_NOW_PLAYING: {
            ATTR_EVENT: event,
            ATTR_TIMESTAMP: timestamp,
            ATTR_ATTRIBUTES: attributes,
        },
        ATTR_REGISTRATION_INFO: registration_info,
    }


async def async_send(
    hass: HomeAssistant,
    entry: ConfigEntry,
    session_id: str,
    now_playing_token: str,
    event: str,
    timestamp: int,
    attributes: dict[str, Any],
) -> PushResult:
    """Send one `update` or `end`, and classify the answer.

    A relay refusal is a value rather than an exception, because the caller has to keep a session
    alive through a bad relay day. Nothing here logs a token.
    """
    app_data = entry.data.get(ATTR_APP_DATA, {})
    if not app_data.get(ATTR_PUSH_URL) or not app_data.get(ATTR_PUSH_TOKEN):
        # A registration that never had cloud push. Nothing to do and nothing to complain about
        # repeatedly.
        return PushResult(PushOutcome.MISCONFIGURED, error_type="NoPushRegistration")

    body = build_request(entry, now_playing_token, event, timestamp, attributes)
    session = async_get_clientsession(hass)

    try:
        async with asyncio.timeout(RELAY_TIMEOUT_SECONDS):
            response = await session.post(app_data[ATTR_PUSH_URL], json=body)
            status = response.status
            try:
                result = await response.json()
            except ValueError, ClientResponseError:
                result = {}
    except TimeoutError:
        _LOGGER.debug(
            "Timed out sending Remote Now Playing %s for session %s", event, session_id
        )
        return PushResult(PushOutcome.RETRY, error_type="Timeout")
    except ClientError as err:
        _LOGGER.debug(
            "Could not reach the push relay for Remote Now Playing %s (session %s): %s",
            event,
            session_id,
            err,
        )
        return PushResult(PushOutcome.RETRY, error_type="Unreachable")

    if status in (HTTPStatus.OK, HTTPStatus.CREATED, HTTPStatus.ACCEPTED):
        return PushResult(PushOutcome.DELIVERED, status=status)

    error_type = result.get("errorType") if isinstance(result, dict) else None
    outcome = _OUTCOMES.get(error_type) if error_type else None
    if outcome is None:
        # No recognised classification. A server error is worth retrying; anything else is not
        # going to change by repeating it, but it is still not grounds for deleting a token.
        outcome = (
            PushOutcome.RETRY
            if status >= HTTPStatus.INTERNAL_SERVER_ERROR
            else PushOutcome.MISCONFIGURED
        )

    return PushResult(outcome, error_type=error_type, status=status)
