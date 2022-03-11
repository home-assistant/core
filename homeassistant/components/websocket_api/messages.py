"""Message templates for websocket commands."""
from __future__ import annotations

from functools import lru_cache
import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import Event, State
from homeassistant.helpers import config_validation as cv
from homeassistant.util.json import (
    find_paths_unserializable_data,
    format_unserializable_data,
)
from homeassistant.util.yaml.loader import JSON_TYPE

from . import const

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


def event_message(iden: JSON_TYPE, event: Any) -> dict[str, Any]:
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
        add: {entity_id: state,…}
        changed: {entity_id: diff,…}
        removed: [entity_id,…]
    }

    Init state should do as_dict, copy, remove entity id since it will be in the key

    Fetch function is empty
    """
    # The entity_id is also duplicated in the message twice but its actually used
    if (event_new_state := event.data["new_state"]) is None:
        return {"remove": [event.data["entity_id"]]}
    assert isinstance(event_new_state, State)
    if (event_old_state := event.data["old_state"]) is None:
        return {
            "add": {
                event_new_state.entity_id: compressed_state_dict_add(event_new_state)
            }
        }
    assert isinstance(event_old_state, State)
    return _state_diff(event_old_state, event_new_state)


def _state_diff(
    old_state: State, new_state: State
) -> dict[str, dict[str, dict[str, dict[str, str | list[str]]]]]:
    """Create a diff dict that can be used to overlay changes."""
    diff: dict = {"+": {}}
    additions = diff["+"]
    if old_state.state != new_state.state:
        additions["s"] = new_state.state
    if old_state.last_changed != new_state.last_changed:
        additions["lc"] = new_state.last_changed.timestamp()
    elif old_state.last_updated != new_state.last_updated:
        additions["lu"] = new_state.last_updated.timestamp()
    if old_state.context.id != new_state.context.id:
        additions.setdefault("c", {})["id"] = new_state.context.id
    if old_state.context.parent_id != new_state.context.parent_id:
        additions.setdefault("c", {})["parent_id"] = new_state.context.parent_id
    if old_state.context.user_id != new_state.context.user_id:
        additions.setdefault("c", {})["user_id"] = new_state.context.user_id
    old_attributes = old_state.attributes
    for key, value in new_state.attributes.items():
        if old_attributes.get(key) != value:
            additions.setdefault("a", {})[key] = value
    if removed := set(old_attributes).difference(new_state.attributes):
        diff["-"] = {"a": removed}
    return {"changed": {new_state.entity_id: diff}}


def compressed_state_dict_add(state: State) -> dict[str, Any]:
    """Build a compressed dict of a state for adds.

    Omits the lu (last_updated) if it matches (lc) last_changed.

    Sends c (context) as a string if it only contains an id.
    """
    state_dict = state.as_compressed_dict().copy()
    if state_dict["lu"] == state_dict["lc"]:
        del state_dict["lu"]
    if state_dict["c"]["parent_id"] is None and state_dict["c"]["user_id"] is None:
        state_dict["c"] = state_dict["c"]["id"]
    return state_dict


def message_to_json(message: dict[str, Any]) -> str:
    """Serialize a websocket message to json."""
    try:
        return const.JSON_DUMP(message)
    except (ValueError, TypeError):
        _LOGGER.error(
            "Unable to serialize to JSON. Bad data found at %s",
            format_unserializable_data(
                find_paths_unserializable_data(message, dump=const.JSON_DUMP)
            ),
        )
        return const.JSON_DUMP(
            error_message(
                message["id"], const.ERR_UNKNOWN_ERROR, "Invalid JSON in response"
            )
        )
