"""Support for bemfa ervice."""

from __future__ import annotations

from collections.abc import Mapping
import hashlib
import logging
from typing import Any

from .const import MSG_OFF, MSG_ON, MSG_SEPARATOR, TOPIC_PREFIX
from .entities_config import ENTITIES_CONFIG, GENERATE, RESOLVE, SUFFIX

_LOGGING = logging.getLogger(__name__)


def generate_topic(domain: str, entity_id: str) -> str:
    """Generate topic by hass entity id."""
    suffix = ENTITIES_CONFIG[domain][SUFFIX]

    # bemfa topic supports only alphanumeric, md5 generates unique alphanumeric string of each entity id regardless of its format.
    return TOPIC_PREFIX + hashlib.md5(entity_id.encode("utf-8")).hexdigest() + suffix


def generate_msg_list(
    domain: str, state: str, attributes: Mapping[str, Any]
) -> list[str]:
    """Generate msg_list from hass state."""
    generate_funs = ENTITIES_CONFIG[domain][GENERATE]

    # if first one is off, the following others is not necessary
    msg_list = [generate_funs[0](state, attributes)]
    if msg_list[0] != MSG_OFF:
        msg_list += list(
            map(
                lambda f: f(state, attributes),
                generate_funs[1:],
            )
        )
    while len(msg_list) > 0 and msg_list[len(msg_list) - 1] == "":
        msg_list.pop()

    return msg_list


def generate_msg(domain: str, state: str, attributes: Mapping[str, Any]) -> str:
    """Generate bemfa msg from hass state."""
    return MSG_SEPARATOR.join(map(str, generate_msg_list(domain, state, attributes)))


def resolve_msg(
    domain: str, msg: str, attributes: Mapping[str, Any]
) -> tuple[list[str], list[tuple[int, int, str, Mapping[str, Any]]]]:
    """Resolve bemfa msg to hass service calls."""
    msg_list: list[Any] = msg.split(MSG_SEPARATOR)
    if msg_list[0] == MSG_OFF:
        msg_list = [MSG_OFF]  # discard any data followed by "off"
    elif msg_list[0] == MSG_ON:
        for i in range(1, len(msg_list)):
            msg_list[i] = int(msg_list[i])  # data followed by "on" must be integers
    else:
        return ([], [])
    resolvers = ENTITIES_CONFIG[domain][RESOLVE]
    actions: list[tuple[int, int, str, Mapping[str, Any]]] = []
    for resolver in resolvers:
        if len(msg_list) > resolver[0]:
            action = resolver[2](msg_list[resolver[0] : resolver[1]], attributes)
            actions.append((resolver[0], resolver[1]) + action)

    return (msg_list, actions)
