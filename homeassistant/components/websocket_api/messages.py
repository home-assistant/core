"""Message templates for websocket commands."""
from __future__ import annotations

from copy import copy
from functools import lru_cache
import logging
from typing import Any, Final

import voluptuous as vol

from homeassistant.core import Context, Event
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

NULL_DICT: dict[str, str] = {}


class NullContext(Context):
    """A null context."""

    def as_dict(self) -> dict:
        """Return an empty dict for a null context."""
        return NULL_DICT


NULL_CONTEXT = NullContext()


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


def cached_state_changed_event_message(iden: int, event: Event) -> str:
    """Return an event message.

    Serialize to json once per message.

    Since we can have many clients connected that are
    all getting many of the same events (mostly state changed)
    we can avoid serializing the same data for each connection.
    """
    return _cached_state_changed_event_message(event).replace(
        IDEN_JSON_TEMPLATE, str(iden), 1
    )


@lru_cache(maxsize=128)
def _cached_state_changed_event_message(event: Event) -> str:
    """Cache and serialize the event to json.

    The IDEN_TEMPLATE is used which will be replaced
    with the actual iden in cached_event_message
    """
    new_state = copy(event.data["new_state"])
    event_copy = copy(event)
    new_state.context = NULL_CONTEXT
    event_copy.data["old_state"] = None
    event_copy.data["context"] = NULL_CONTEXT
    event_copy.data["new_state"] = new_state
    # We likely don't need event_copy.time_fired either since last_updated on the new_state is the same
    # We only need event.context as its the same for the new_state
    # The entity_id is also duplicated in the message twice but its actually used
    return message_to_json(event_message(IDEN_TEMPLATE, event_copy))


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
