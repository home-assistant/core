"""Typing Helpers for Home Assistant."""
from enum import Enum
from typing import Any, Dict, Mapping, Optional, Tuple, Union

import homeassistant.core

GPSType = Tuple[float, float]
ConfigType = Dict[str, Any]
ContextType = homeassistant.core.Context
DiscoveryInfoType = Dict[str, Any]
EventType = homeassistant.core.Event
ServiceCallType = homeassistant.core.ServiceCall
ServiceDataType = Dict[str, Any]
StateType = Union[None, str, int, float]
TemplateVarsType = Optional[Mapping[str, Any]]

# HomeAssistantType is not to be used,
# It is not present in the core code base.
# It is kept in order not to break custom components
# In due time it will be removed.
HomeAssistantType = homeassistant.core.HomeAssistant

# Custom type for recorder Queries
QueryType = Any


class UndefinedType(Enum):
    """Singleton type for use with not set sentinel values."""

    _singleton = 0


UNDEFINED = UndefinedType._singleton  # pylint: disable=protected-access
