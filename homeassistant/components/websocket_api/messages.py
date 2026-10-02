"""Message templates for websocket commands."""

from functools import lru_cache
import logging
from typing import Any, Final, cast

import probatio

from homeassistant.const import (
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_CONTEXT,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
)
from homeassistant.core import CompressedState, Event, EventStateChangedData
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import (
    JSON_DUMP,
    find_paths_unserializable_data,
    json_bytes,
)
from homeassistant.util.json import format_unserializable_data

from . import const

_LOGGER: Final = logging.getLogger(__name__)

# Minimal requirements of a message
MINIMAL_MESSAGE_SCHEMA: Final = probatio.Schema(
    {probatio.Required("id"): cv.positive_int, probatio.Required("type"): cv.string},
    extra=probatio.ALLOW_EXTRA,
)

# Base schema to extend by message handlers
BASE_COMMAND_MESSAGE_SCHEMA: Final = probatio.Schema(
    {probatio.Required("id"): cv.positive_int}
)

STATE_DIFF_ADDITIONS = "+"
STATE_DIFF_REMOVALS = "-"

ENTITY_EVENT_ADD = "a"
ENTITY_EVENT_REMOVE = "r"
ENTITY_EVENT_CHANGE = "c"

BASE_ERROR_MESSAGE = {
    "type": const.TYPE_RESULT,
    "success": False,
}

INVALID_JSON_PARTIAL_MESSAGE = json_bytes(
    {
        **BASE_ERROR_MESSAGE,
        "error": {
            "code": const.ERR_UNKNOWN_ERROR,
            "message": "Invalid JSON in response",
        },
    }
)


def result_message(iden: int, result: Any = None) -> dict[str, Any]:
    """Return a success result message."""
    return {"id": iden, "type": const.TYPE_RESULT, "success": True, "result": result}


def construct_result_message(iden: int, payload: bytes) -> bytes:
    """Construct a success result message JSON."""
    return b"".join(
        (
            b'{"id":',
            str(iden).encode(),
            b',"type":"result","success":true,"result":',
            payload,
            b"}",
        )
    )


def error_message(
    iden: int | None,
    code: str,
    message: str,
    translation_key: str | None = None,
    translation_domain: str | None = None,
    translation_placeholders: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return an error result message."""
    error_payload: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    # In case `translation_key` is `None` we do not set it, nor the
    # `translation`_placeholders` and `translation_domain`.
    if translation_key is not None:
        error_payload["translation_key"] = translation_key
        error_payload["translation_placeholders"] = translation_placeholders
        error_payload["translation_domain"] = translation_domain
    return {
        "id": iden,
        **BASE_ERROR_MESSAGE,
        "error": error_payload,
    }


def event_message(iden: int, event: Any) -> dict[str, Any]:
    """Return an event message."""
    return {"id": iden, "type": "event", "event": event}


def construct_event_message(iden: int, event: bytes) -> bytes:
    """Construct an event message JSON."""
    return b"".join(
        (
            b'{"id":',
            str(iden).encode(),
            b',"type":"event","event":',
            event,
            b"}",
        )
    )


def cached_event_message(message_id_as_bytes: bytes, event: Event) -> bytes:
    """Return an event message.

    Serialize to json once per message.

    Since we can have many clients connected that are
    all getting many of the same events (mostly state changed)
    we can avoid serializing the same data for each connection.
    """
    return b"".join(
        (
            _partial_cached_event_message(event),
            b',"id":',
            message_id_as_bytes,
            b"}",
        )
    )


@lru_cache(maxsize=128)
def _partial_cached_event_message(event: Event) -> bytes:
    """Cache and serialize the event to json.

    The message is cached without the trailing "}" and without the id, both of
    which are appended in cached_event_message. Trimming here means the slice
    happens once per event instead of once per subscriber.
    """
    return (
        _message_to_json_bytes_or_none({"type": "event", "event": event.json_fragment})
        or INVALID_JSON_PARTIAL_MESSAGE
    )[:-1]


def cached_state_diff_message(
    message_id_as_bytes: bytes, event: Event[EventStateChangedData]
) -> bytes:
    """Return an event message.

    Serialize to json once per message.

    Since we can have many clients connected that are
    all getting many of the same events (mostly state changed)
    we can avoid serializing the same data for each connection.
    """
    return b"".join(
        (
            _partial_cached_state_diff_message(event),
            b',"id":',
            message_id_as_bytes,
            b"}",
        )
    )


@lru_cache(maxsize=128)
def _partial_cached_state_diff_message(event: Event[EventStateChangedData]) -> bytes:
    """Cache and serialize the event to json.

    The message is cached without the trailing "}" and without the id, both of
    which are appended in cached_state_diff_message. Trimming here means the
    slice happens once per event instead of once per subscriber.
    """
    return (
        _message_to_json_bytes_or_none(
            {"type": "event", "event": _state_diff_event(event)}
        )
        or INVALID_JSON_PARTIAL_MESSAGE
    )[:-1]


def batched_state_diff_message(
    message_id_as_bytes: bytes, events: list[Event[EventStateChangedData]]
) -> bytes:
    """Return one event message carrying several state changes.

    The state update format already describes any number of entities at once, but
    subscribe_entities emitted one message per state change, so a client applying an
    update had to walk its whole state machine once per changed entity rather than once
    per batch. On a large installation that is the dominant cost of running the
    frontend at all.

    Serialization stays shared between connections: each event is still serialized once
    into a cached fragment, and this only joins the fragments, which is why batching
    does not trade one cost for another when many clients are subscribed.
    """
    if len(events) == 1:
        return cached_state_diff_message(message_id_as_bytes, events[0])

    # Grouped rather than appended, because the format keys additions, removals and
    # changes separately. Insertion order is preserved per group, and a caller must not
    # place two updates for the same entity in one batch - see _StateDiffBatch, which
    # flushes instead, since the groups are applied by the client in a fixed order that
    # need not match the order the events happened in.
    grouped: dict[bytes, list[bytes]] = {}
    for event in events:
        key, fragment = _cached_state_diff_fragment(event)
        grouped.setdefault(key, []).append(fragment)

    parts: list[bytes] = [b'{"id":', message_id_as_bytes, b',"type":"event","event":{']
    first = True
    for key, fragments in grouped.items():
        if not first:
            parts.append(b",")
        first = False
        opening, closing = (b'":[', b"]") if key == _REMOVE_KEY else (b'":{', b"}")
        parts.extend((b'"', key, opening, b",".join(fragments), closing))
    parts.append(b"}}")
    return b"".join(parts)


_REMOVE_KEY: Final = ENTITY_EVENT_REMOVE.encode()


@lru_cache(maxsize=128)
def _cached_state_diff_fragment(
    event: Event[EventStateChangedData],
) -> tuple[bytes, bytes]:
    """Cache and serialize one state change as a fragment of a batched message.

    Returns the group the change belongs to - "a", "r" or "c" - and the serialized
    entry that goes inside it, so several changes can be joined into one message
    without any of them being serialized a second time.

    Cached on the event for the same reason _partial_cached_state_diff_message is: with
    many connections subscribed, the same change would otherwise be serialized once per
    connection.
    """
    diff = _state_diff_event(event)
    key = next(iter(diff))
    value = diff[key]
    if key == ENTITY_EVENT_REMOVE:
        # {"r": ["light.kitchen"]} -> b'"light.kitchen"'
        removed = cast(list[str], value)
        return _REMOVE_KEY, json_bytes(removed[0])
    # {"c": {"light.kitchen": diff}} -> b'"light.kitchen":{...}'
    entity_id, payload = next(iter(cast(dict[str, Any], value).items()))
    return key.encode(), b"".join((json_bytes(entity_id), b":", json_bytes(payload)))


def _state_diff_event(
    event: Event[EventStateChangedData],
) -> dict[
    str,
    list[str]
    | dict[str, CompressedState]
    | dict[str, dict[str, dict[str, str | list[str]]]],
]:
    """Convert a state_changed event to the minimal version.

    State update example

    {
        "a": {entity_id: compressed_state,…}
        "c": {entity_id: diff,…}
        "r": [entity_id,…]
    }
    """
    if (new_state := event.data["new_state"]) is None:
        return {ENTITY_EVENT_REMOVE: [event.data["entity_id"]]}
    if (old_state := event.data["old_state"]) is None:
        return {ENTITY_EVENT_ADD: {new_state.entity_id: new_state.as_compressed_state}}
    additions: dict[str, Any] = {}
    diff: dict[str, dict[str, Any]] = {STATE_DIFF_ADDITIONS: additions}
    new_state_context = new_state.context
    old_state_context = old_state.context
    if old_state.state != new_state.state:
        additions[COMPRESSED_STATE_STATE] = new_state.state
    if old_state.last_changed != new_state.last_changed:
        additions[COMPRESSED_STATE_LAST_CHANGED] = new_state.last_changed_timestamp
    elif old_state.last_updated_timestamp != new_state.last_updated_timestamp:
        additions[COMPRESSED_STATE_LAST_UPDATED] = new_state.last_updated_timestamp
    if old_state_context.parent_id != new_state_context.parent_id:
        additions[COMPRESSED_STATE_CONTEXT] = {"parent_id": new_state_context.parent_id}
    if old_state_context.user_id != new_state_context.user_id:
        if COMPRESSED_STATE_CONTEXT in additions:
            additions[COMPRESSED_STATE_CONTEXT]["user_id"] = new_state_context.user_id
        else:
            additions[COMPRESSED_STATE_CONTEXT] = {"user_id": new_state_context.user_id}
    if old_state_context.id != new_state_context.id:
        if COMPRESSED_STATE_CONTEXT in additions:
            additions[COMPRESSED_STATE_CONTEXT]["id"] = new_state_context.id
        else:
            additions[COMPRESSED_STATE_CONTEXT] = new_state_context.id
    if (old_attributes := old_state.attributes) != (
        new_attributes := new_state.attributes
    ):
        if added := {
            key: value
            for key, value in new_attributes.items()
            if key not in old_attributes or old_attributes[key] != value
        }:
            additions[COMPRESSED_STATE_ATTRIBUTES] = added
        if removed := old_attributes.keys() - new_attributes:
            # sets are not JSON serializable by default so we convert to list
            # here if there are any values to avoid jumping
            # into the json_encoder_default
            # for every state diff with a removed attribute
            diff[STATE_DIFF_REMOVALS] = {COMPRESSED_STATE_ATTRIBUTES: list(removed)}
    return {ENTITY_EVENT_CHANGE: {new_state.entity_id: diff}}


def _message_to_json_bytes_or_none(message: dict[str, Any]) -> bytes | None:
    """Serialize a websocket message to json or return None."""
    try:
        return json_bytes(message)
    except ValueError, TypeError:
        _LOGGER.error(
            "Unable to serialize to JSON. Bad data found at %s",
            format_unserializable_data(
                find_paths_unserializable_data(message, dump=JSON_DUMP)
            ),
        )
    return None


def message_to_json_bytes(message: dict[str, Any]) -> bytes:
    """Serialize a websocket message to json or return an error."""
    return _message_to_json_bytes_or_none(message) or json_bytes(
        error_message(
            message["id"], const.ERR_UNKNOWN_ERROR, "Invalid JSON in response"
        )
    )
