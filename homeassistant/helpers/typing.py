"""Typing Helpers for Home Assistant."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any

import homeassistant.core

GPSType = tuple[float, float]
ConfigType = dict[str, Any]
ContextType = homeassistant.core.Context
DiscoveryInfoType = dict[str, Any]
EventType = homeassistant.core.Event
ServiceDataType = dict[str, Any]
StateType = str | int | float | None
TemplateVarsType = Mapping[str, Any] | None

# Custom type for recorder Queries
QueryType = Any

JsonValueType = Union[
    None,
    str,
    int,
    float,
    bool,
    Sequence["JsonValueType"],
    Mapping[str, "JsonValueType"],
]
JsonObjectType = Mapping[str, JsonValueType]


class UndefinedType(Enum):
    """Singleton type for use with not set sentinel values."""

    _singleton = 0


UNDEFINED = UndefinedType._singleton  # pylint: disable=protected-access


# The following types should not used and
# are not present in the core code base.
# They are kept in order not to break custom integrations
# that may rely on them.
# In due time they will be removed.
HomeAssistantType = homeassistant.core.HomeAssistant
ServiceCallType = homeassistant.core.ServiceCall
