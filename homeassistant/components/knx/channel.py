"""Channel registry for KNX entity links.

A channel maps one controllable aspect of a Home Assistant entity (e.g. a switch's on/off
state) to a KNX datapoint with a fixed DPT and a predictable Home Assistant service call.
Channel behaviour is defined statically per platform here; the UI only picks the group
addresses. This keeps encode/decode symmetric (no value templates).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from xknx import XKNX
from xknx.remote_value import GroupAddressesType, RemoteValue, RemoteValueSwitch

from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import State


@dataclass(slots=True)
class LinkServiceCall:
    """A Home Assistant service call resolved from an incoming KNX telegram."""

    domain: str
    service: str
    data: dict[str, Any]


@dataclass(frozen=True)
class ChannelDefinition:
    """Static definition of an entity-link channel role for a platform.

    ``remote_value_factory`` is called with the status group address (HA state -> KNX) and
    the command group addresses (KNX -> HA action).
    """

    remote_value_factory: Callable[[XKNX, str | None, list[str]], RemoteValue]
    read_state: Callable[[State], Any | None]
    to_service_call: Callable[[str, Any], LinkServiceCall | None]


def _switch_remote_value(
    xknx: XKNX, status_ga: str | None, command_gas: list[str]
) -> RemoteValueSwitch:
    return RemoteValueSwitch(
        xknx,
        group_address=status_ga,
        # validated group address strings are accepted by xknx as GroupAddressesType
        group_address_state=cast(GroupAddressesType, command_gas) or None,
        sync_state=False,
    )


def _switch_read_state(state: State) -> bool | None:
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


CHANNELS: dict[Platform, dict[str, ChannelDefinition]] = {
    Platform.SWITCH: {
        "switch": ChannelDefinition(
            remote_value_factory=_switch_remote_value,
            read_state=_switch_read_state,
            to_service_call=_switch_service_call,
        ),
    },
}
