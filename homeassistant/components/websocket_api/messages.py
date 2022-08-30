"""Message templates for websocket commands."""
from __future__ import annotations

from functools import lru_cache
import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import Event, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import JSON_DUMP
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)
from homeassistant.util.yaml.loader import JSON_TYPE

from . import const
from .const import (
    COMPRESSED_STATE_ATTRIBUTES,
    COMPRESSED_STATE_CONTEXT,
    COMPRESSED_STATE_LAST_CHANGED,
    COMPRESSED_STATE_LAST_UPDATED,
    COMPRESSED_STATE_STATE,
)

_LOGGER: Final = logging.getLogger(__name__)

# Minimal requirements of a message
MINIMAL_MESSAGE_SCHEMA: Final = vol.Schema(
    {vol.Required("id"): cv.positive_int, vol.Required("type"): cv.string},
    extra=vol.ALLOW_EXTRA,
)

# Base schema to extend by message handlers
BASE_COMMAND_MESSAGE_SCHEMA: Final = vol.Schema({vol.Required("id"): cv.positive_int})

IDEN_TEMPLATE: Final = "__IDEN__"
IDEN_JSON_TEMPLATE: Final = '"__IDEN__"'

STATE_DIFF_ADDITIONS = "+"
STATE_DIFF_REMOVALS = "-"

ENTITY_EVENT_ADD = "a"
ENTITY_EVENT_REMOVE = "r"
ENTITY_EVENT_CHANGE = "c"


def result_message(iden: int, result: Any = None) -> dict[str, Any]:
    """Return a success result message."""
    return {"id": iden, "type": const.TYPE_RESULT, "success": True, "result": result}


def error_message(iden: int | None, code: str, message: str) -> dict[str, Any]:
    """Return an error result message."""
    return {
        "id": iden,
        "type": const.TYPE_RESULT,
        "success": False,
        "error": {"code": code, "message": message},
    }


def event_message(iden: JSON_TYPE | int, event: Any) -> dict[str, Any]:
    """Return an event message."""
    return {"id": iden, "type": "event", "event": event}


def cached_event_message(iden: int, event: Event) -> str:
    """Return an event message.

    Serialize to json once per message.

    Since we can have many clients connected that are
    all getting many of the same events (mostly state changed)
    we can avoid serializing the same data for each connection.
    """
    return _cached_event_message(event).replace(IDEN_JSON_TEMPLATE, str(iden), 1)


@lru_cache(maxsize=128)
def _cached_event_message(event: Event) -> str:
    """Cache and serialize the event to json.

    The IDEN_TEMPLATE is used which will be replaced
    with the actual iden in cached_event_message
    """
    return message_to_json(event_message(IDEN_TEMPLATE, event))


def cached_state_diff_message(iden: int, event: Event) -> str:
    """Return an event message.

    Serialize to json once per message.

    Since we can have many clients connected that are
    all getting many of the same events (mostly state changed)
    we can avoid serializing the same data for each connection.
    """
    return _cached_state_diff_message(event).replace(IDEN_JSON_TEMPLATE, str(iden), 1)


@lru_cache(maxsize=128)
def _cached_state_diff_message(event: Event) -> str:
    """Cache and serialize the event to json.

    The IDEN_TEMPLATE is used which will be replaced
    with the actual iden in cached_event_message
    """
    return message_to_json(event_message(IDEN_TEMPLATE, _state_diff_event(event)))


def _state_diff_event(event: Event) -> dict:
    """Convert a state_changed event to the minimal version.

    State update example

    {
        "a": {entity_id: compressed_state,…}
        "c": {entity_id: diff,…}
        "r": [entity_id,…]
    }
    """
    if (event_new_state := event.data["new_state"]) is None:
        return {ENTITY_EVENT_REMOVE: [event.data["entity_id"]]}
    assert isinstance(event_new_state, State)
    if (event_old_state := event.data["old_state"]) is None:
        return {
            ENTITY_EVENT_ADD: {
                event_new_state.entity_id: compressed_state_dict_add(event_new_state)
            }
        }
    assert isinstance(event_old_state, State)
    return _state_diff(event_old_state, event_new_state)


def _state_diff(
    old_state: State, new_state: State
) -> dict[str, dict[str, dict[str, dict[str, str | list[str]]]]]:
    """Create a diff dict that can be used to overlay changes."""
    diff: dict = {STATE_DIFF_ADDITIONS: {}}
    additions = diff[STATE_DIFF_ADDITIONS]
    if old_state.state != new_state.state:
        additions[COMPRESSED_STATE_STATE] = new_state.state
    if old_state.last_changed != new_state.last_changed:
        additions[COMPRESSED_STATE_LAST_CHANGED] = new_state.last_changed.timestamp()
    elif old_state.last_updated != new_state.last_updated:
        additions[COMPRESSED_STATE_LAST_UPDATED] = new_state.last_updated.timestamp()
    if old_state.context.parent_id != new_state.context.parent_id:
        additions.setdefault(COMPRESSED_STATE_CONTEXT, {})[
            "parent_id"
        ] = new_state.context.parent_id
    if old_state.context.user_id != new_state.context.user_id:
        additions.setdefault(COMPRESSED_STATE_CONTEXT, {})[
            "user_id"
        ] = new_state.context.user_id
    if old_state.context.id != new_state.context.id:
        if COMPRESSED_STATE_CONTEXT in additions:
            additions[COMPRESSED_STATE_CONTEXT]["id"] = new_state.context.id
        else:
            additions[COMPRESSED_STATE_CONTEXT] = new_state.context.id
    old_attributes = old_state.attributes
    for key, value in new_state.attributes.items():
        if old_attributes.get(key) != value:
            additions.setdefault(COMPRESSED_STATE_ATTRIBUTES, {})[key] = value
    if removed := set(old_attributes).difference(new_state.attributes):
        diff[STATE_DIFF_REMOVALS] = {COMPRESSED_STATE_ATTRIBUTES: removed}
    return {ENTITY_EVENT_CHANGE: {new_state.entity_id: diff}}


def compressed_state_dict_add(state: State) -> dict[str, Any]:
    """Build a compressed dict of a state for adds.

    Omits the lu (last_updated) if it matches (lc) last_changed.

    Sends c (context) as a string if it only contains an id.
    """
    if state.context.parent_id is None and state.context.user_id is None:
        context: dict[str, Any] | str = state.context.id
    else:
        context = state.context.as_dict()
    compressed_state: dict[str, Any] = {
        COMPRESSED_STATE_STATE: state.state,
        COMPRESSED_STATE_ATTRIBUTES: state.attributes,
        COMPRESSED_STATE_CONTEXT: context,
        COMPRESSED_STATE_LAST_CHANGED: state.last_changed.timestamp(),
    }
    if state.last_changed != state.last_updated:
        compressed_state[COMPRESSED_STATE_LAST_UPDATED] = state.last_updated.timestamp()
    return compressed_state


def message_to_json(message: dict[str, Any]) -> str:
    """Serialize a websocket message to json."""
    try:
        return JSON_DUMP(message)
    except (ValueError, TypeError):
        _LOGGER.error(
            "Unable to serialize to JSON. Bad data found at %s",
            format_unserializable_data(
                find_paths_unserializable_data(message, dump=JSON_DUMP)
            ),
        )
        return JSON_DUMP(
            error_message(
                message["id"], const.ERR_UNKNOWN_ERROR, "Invalid JSON in response"
            )
        )
