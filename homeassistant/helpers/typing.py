"""Typing Helpers for Home Assistant."""

from collections.abc import Mapping
from enum import Enum
from functools import partial
from typing import Any, Never

import homeassistant.core

from .deprecation import (
    DeprecatedAlias,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

GPSType = tuple[float, float]
ConfigType = dict[str, Any]
DiscoveryInfoType = dict[str, Any]
ServiceDataType = dict[str, Any]
StateType = str | int | float | None
TemplateVarsType = Mapping[str, Any] | None
NoEventData = Mapping[str, Never]

# Custom type for recorder Queries
QueryType = Any


class UndefinedType(Enum):
    """Singleton type for use with not set sentinel values."""

    _singleton = 0


UNDEFINED = UndefinedType._singleton  # pylint: disable=protected-access


# The following types should not used and
# are not present in the core code base.
# They are kept in order not to break custom integrations
# that may rely on them.
# Deprecated as of 2024.5 use types from homeassistant.core instead.
_DEPRECATED_ContextType = DeprecatedAlias(
    homeassistant.core.Context, "homeassistant.core.Context", "2025.5"
)
_DEPRECATED_EventType = DeprecatedAlias(
    homeassistant.core.Event, "homeassistant.core.Event", "2025.5"
)
_DEPRECATED_HomeAssistantType = DeprecatedAlias(
    homeassistant.core.HomeAssistant, "homeassistant.core.HomeAssistant", "2025.5"
)
_DEPRECATED_ServiceCallType = DeprecatedAlias(
    homeassistant.core.ServiceCall, "homeassistant.core.ServiceCall", "2025.5"
)

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
