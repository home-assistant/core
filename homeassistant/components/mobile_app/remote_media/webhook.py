"""Webhook commands the iOS app uses to register and retire a Follow relationship.

Both arrive over the ordinary encrypted `mobile_app` webhook, so the registration that owns a
session is the authenticated config entry that sent the request. The payload chooses only which
`media_player` to follow, never which registration to attach to.

Not simply "last write wins": registration happens in a process whose lifetime the app does not
control, so one describing a relationship the user has already replaced can arrive after its
replacement's. Arrival order is a guess about that; the app's monotonic Follow sequence is not.
"""

import hashlib
import logging
from typing import Any

from aiohttp.web import Response
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from ..helpers import empty_okay_response
from ..webhook import WEBHOOK_COMMANDS, WEBHOOK_PAYLOAD_REDACTORS, validate_schema
from .const import (
    ATTR_GENERATION,
    ATTR_GENERATION_SEQUENCE,
    ATTR_PUSH_TOKEN,
    ATTR_SCHEMA_VERSION,
    ATTR_SERVER_ID_KEY,
    ATTR_SESSION_ID,
    MAX_GENERATION_LENGTH,
    MAX_GENERATION_SEQUENCE,
    MAX_PUSH_TOKEN_LENGTH,
    MAX_SERVER_ID_LENGTH,
    MAX_SESSION_ID_LENGTH,
    SUPPORTED_SCHEMA_VERSIONS,
    WEBHOOK_TYPE_DISMISSED,
    WEBHOOK_TYPE_TOKEN,
)
from .manager import async_get_manager
from .mapper import MEDIA_PLAYER_PREFIX
from .model import RemoteMediaSession
from .store import async_load_sessions, async_save_session

_LOGGER = logging.getLogger(__name__)

TOKEN_FINGERPRINT_LENGTH = 16


def _bounded_string(maximum: int) -> vol.All:
    """A non-empty string no longer than `maximum`."""
    return vol.All(cv.string, vol.Length(min=1, max=maximum))


def _media_player_entity_id(value: Any) -> str:
    """Validate a followed player.

    Only `media_player` entities, so a registration cannot turn into a subscription to arbitrary
    parts of the state machine.
    """
    entity_id = cv.entity_id(value)
    if not entity_id.startswith(MEDIA_PLAYER_PREFIX):
        raise vol.Invalid("Remote Now Playing can only follow a media_player entity")
    return entity_id


def valid_token(value: Any) -> str | None:
    """Return the APNs update token if it is usable, else None.

    Deliberately not a voluptuous validator: `validate_schema` reports a failure with
    `humanize_error`, which echoes the offending value into an ERROR log that is on by default. A
    rejected token would then be more exposed than an accepted one.
    """
    if not isinstance(value, str) or not value or len(value) > MAX_PUSH_TOKEN_LENGTH:
        return None
    if len(value) % 2 or not all(
        character in "0123456789abcdefABCDEF" for character in value
    ):
        return None
    return value


def token_fingerprint(token: str) -> str:
    """A short, non-reversible label for a session token.

    Enough to correlate a session across log lines without the log becoming a place to harvest
    APNs destinations from.
    """
    return hashlib.sha256(token.encode()).hexdigest()[:TOKEN_FINGERPRINT_LENGTH]


@WEBHOOK_PAYLOAD_REDACTORS.register(WEBHOOK_TYPE_TOKEN)
def redact_token_payload(payload: Any) -> Any:
    """Replace the session token before the payload reaches the debug log.

    `mobile_app` logs every decrypted webhook payload at debug level, and this one carries a live
    APNs destination for the user's device.
    """
    if not isinstance(payload, dict) or ATTR_PUSH_TOKEN not in payload:
        return payload
    token = payload[ATTR_PUSH_TOKEN]
    redacted = (
        f"**REDACTED:{token_fingerprint(token)}**"
        if isinstance(token, str)
        else "**REDACTED**"
    )
    return {**payload, ATTR_PUSH_TOKEN: redacted}


@WEBHOOK_COMMANDS.register(WEBHOOK_TYPE_TOKEN)
@validate_schema(
    {
        vol.Required(ATTR_SESSION_ID): _bounded_string(MAX_SESSION_ID_LENGTH),
        vol.Required(ATTR_SERVER_ID_KEY): _bounded_string(MAX_SERVER_ID_LENGTH),
        vol.Required(ATTR_ENTITY_ID): _media_player_entity_id,
        vol.Required(ATTR_GENERATION): _bounded_string(MAX_GENERATION_LENGTH),
        vol.Required(ATTR_GENERATION_SEQUENCE): vol.All(
            cv.positive_int, vol.Range(min=1, max=MAX_GENERATION_SEQUENCE)
        ),
        # Any value: validated in the handler so a bad one is never echoed into a log.
        vol.Required(ATTR_PUSH_TOKEN): object,
        vol.Required(ATTR_SCHEMA_VERSION): vol.All(
            cv.positive_int, vol.In(SUPPORTED_SCHEMA_VERSIONS)
        ),
    }
)
async def webhook_remote_media_session_token(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Store the APNs update token for one Follow relationship and start watching its player."""
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    session_id = data[ATTR_SESSION_ID]
    entity_id = data[ATTR_ENTITY_ID]
    server_id = data[ATTR_SERVER_ID_KEY]
    generation = data[ATTR_GENERATION]
    sequence = data[ATTR_GENERATION_SEQUENCE]

    if (token := valid_token(data[ATTR_PUSH_TOKEN])) is None:
        _LOGGER.warning(
            "Ignoring a Remote Now Playing registration for %s: its update token is not"
            " hexadecimal data of a usable length",
            entity_id,
        )
        return empty_okay_response()

    manager = async_get_manager(hass)
    stored = {
        session.session_id: session for session in async_load_sessions(hass, webhook_id)
    }
    previous = stored.get(session_id)

    if previous is not None and previous.generation_sequence is not None:
        if sequence < previous.generation_sequence:
            # A registration from a relationship the user has already replaced, arriving late.
            # Nothing about it is applied: not the token, not the entity, not the sticky state,
            # not the ordering clock, and no listener is moved.
            _LOGGER.debug(
                "Ignoring a stale Remote Now Playing registration for session %s: it names"
                " Follow %s, and %s is current",
                session_id,
                sequence,
                previous.generation_sequence,
            )
            return empty_okay_response()

        if (
            sequence == previous.generation_sequence
            and previous.generation != generation
        ):
            # Two relationships claiming one place in the order. The app increments the counter
            # once per relationship, so this should be impossible; guessing which is newer would
            # be exactly the heuristic the sequence exists to avoid.
            _LOGGER.warning(
                "Ignoring a conflicting Remote Now Playing registration for %s: Follow %s is"
                " already held by a different session lifetime",
                entity_id,
                sequence,
            )
            return empty_okay_response()

    if previous is not None and previous.describes_same_lifetime(generation, sequence):
        if (
            previous.push_token == token
            and previous.entity_id == entity_id
            and previous.server_id == server_id
            and manager.async_is_known(webhook_id, session_id)
        ):
            # The same registration again: idempotent. No second listener, no second initial push.
            return empty_okay_response()
        # The same relationship with a replacement token: the card on the phone is the same card,
        # so it keeps its sticky state and its ordering clock, and the old token is never used
        # again. A registration is what supersedes a token; no dismissal is involved.
        carried_over = previous
    else:
        carried_over = None
        if previous is not None:
            # A later relationship reusing the session identifier, which happens whenever the user
            # follows the same player again. Nothing of the old one is carried: the track it was
            # showing, and the ordering clock the previous APNs session was sequenced by, both
            # belong to a session that has ended. Current state rebuilds the card from scratch.
            _LOGGER.debug(
                "Remote Now Playing session %s moves from Follow %s to %s",
                session_id,
                previous.generation_sequence,
                sequence,
            )

    session = RemoteMediaSession(
        session_id=session_id,
        generation=generation,
        generation_sequence=sequence,
        entity_id=entity_id,
        server_id=server_id,
        push_token=token,
        schema_version=data[ATTR_SCHEMA_VERSION],
    )
    if carried_over is not None:
        session.last_timestamp = carried_over.last_timestamp
        session.last_snapshot = carried_over.last_snapshot

    async_save_session(hass, webhook_id, session)
    # Attaching the listener also reconciles the player's current state, which schedules the
    # first update through the normal publisher path. The webhook does not wait for APNs.
    manager.async_add(webhook_id, session, config_entry, reconcile=True)

    _LOGGER.debug(
        "Following %s for Remote Now Playing (session %s, Follow %s/%s, token %s)",
        entity_id,
        session_id,
        generation,
        sequence,
        token_fingerprint(token),
    )
    return empty_okay_response()


@WEBHOOK_COMMANDS.register(WEBHOOK_TYPE_DISMISSED)
@validate_schema(
    {
        vol.Required(ATTR_SESSION_ID): _bounded_string(MAX_SESSION_ID_LENGTH),
        vol.Required(ATTR_GENERATION): _bounded_string(MAX_GENERATION_LENGTH),
        vol.Required(ATTR_GENERATION_SEQUENCE): vol.All(
            cv.positive_int, vol.Range(min=1, max=MAX_GENERATION_SEQUENCE)
        ),
    }
)
async def webhook_remote_media_session_dismissed(
    hass: HomeAssistant, config_entry: ConfigEntry, data: dict[str, Any]
) -> Response:
    """Stop following, if the dismissal names the relationship that is current.

    A dismissal can arrive long after the fact, because the app writes down what it owes and retries
    on a later launch. Both halves have to match: an older sequence names a relationship that is
    already over, and the same sequence with a different generation is a conflict.
    """
    webhook_id = config_entry.data[CONF_WEBHOOK_ID]
    session_id = data[ATTR_SESSION_ID]
    generation = data[ATTR_GENERATION]
    sequence = data[ATTR_GENERATION_SEQUENCE]

    stored = {
        session.session_id: session for session in async_load_sessions(hass, webhook_id)
    }
    if (session := stored.get(session_id)) is None:
        return empty_okay_response()

    if not session.describes_same_lifetime(generation, sequence):
        # Stopping and immediately re-following the same player reuses the session identifier, so
        # acting on this would take the new relationship's token with it.
        _LOGGER.debug(
            "Ignoring a Remote Now Playing dismissal for session %s: it names Follow %s/%s, but"
            " %s/%s is current",
            session_id,
            generation,
            sequence,
            session.generation,
            session.generation_sequence,
        )
        return empty_okay_response()

    async_get_manager(hass).async_end_session(webhook_id, session_id)
    _LOGGER.debug("Stopped following %s for Remote Now Playing", session.entity_id)
    return empty_okay_response()
