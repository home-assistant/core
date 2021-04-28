"""Typing Helpers for Home Assistant."""
from collections.abc import Iterable
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Mapping, Optional, Tuple, Union

from typing_extensions import Protocol

import homeassistant.core

# Avoid circular dependency.
if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity

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


class AddEntitiesCallback(Protocol):
    """Protocol type for add_entities from homeassistant.helpers.entity_platform."""

    def __call__(
        self, new_entities: Iterable[Entity], update_before_add: bool = False
    ) -> None:
        """Define add_entities type."""
