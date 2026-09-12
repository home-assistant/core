"""Channel registry for KNX entity links.

A channel maps one controllable aspect of a Home Assistant entity (e.g. a switch's on/off
state) to a pair of KNX group addresses with a fixed DPT and a predictable Home Assistant
service call. Channel behaviour is defined statically per platform here; the UI only picks
the group addresses. This keeps encode/decode symmetric (no value templates).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from xknx.dpt import DPTBase, DPTSwitch

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import State

from .storage.const import CONF_GA_COMMAND, CONF_GA_STATUS


@dataclass(slots=True)
class LinkServiceCall:
    """A Home Assistant service call resolved from an incoming KNX telegram."""

    domain: str
    service: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ChannelDefinition:
    """Static definition of an entity-link channel for a platform.

    `status_key` and `command_key` name the group address fields of the platform schema.
    """

    status_key: str
    command_key: str
    dpt: type[DPTBase]
    from_state: Callable[[State], Any | None]
    to_service_call: Callable[[str, Any], LinkServiceCall | None]


def _switch_from_state(state: State) -> bool | None:
    if state.state == STATE_ON:
        return True
    if state.state == STATE_OFF:
        return False
    return None


def _switch_service_call(entity_id: str, value: bool) -> LinkServiceCall:
    return LinkServiceCall(
        domain=Platform.SWITCH,
        service=SERVICE_TURN_ON if value else SERVICE_TURN_OFF,
        data={ATTR_ENTITY_ID: entity_id},
    )


CHANNELS: dict[Platform, tuple[ChannelDefinition, ...]] = {
    Platform.SWITCH: (
        ChannelDefinition(
            status_key=CONF_GA_STATUS,
            command_key=CONF_GA_COMMAND,
            dpt=DPTSwitch,
            from_state=_switch_from_state,
            to_service_call=_switch_service_call,
        ),
    ),
}
