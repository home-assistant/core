"""Typing Helpers for Home Assistant."""

from collections.abc import Mapping
from enum import Enum
from functools import partial
from typing import Any, Never

import voluptuous as vol

from .deprecation import (
    DeferredDeprecatedAlias,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

type GPSType = tuple[float, float]
type ConfigType = dict[str, Any]
type DiscoveryInfoType = dict[str, Any]
type ServiceDataType = dict[str, Any]
type StateType = str | int | float | None
type TemplateVarsType = Mapping[str, Any] | None
type NoEventData = Mapping[str, Never]
type VolSchemaType = vol.Schema | vol.All | vol.Any
type VolDictType = dict[str | vol.Marker, Any]

# Custom type for recorder Queries
type QueryType = Any


class UndefinedType(Enum):
    """Singleton type for use with not set sentinel values."""

    _singleton = 0


UNDEFINED = UndefinedType._singleton  # noqa: SLF001


def _deprecated_typing_helper(attr: str) -> DeferredDeprecatedAlias:
    """Help to make a DeferredDeprecatedAlias."""

    def value_fn() -> Any:
        # pylint: disable-next=import-outside-toplevel
        import homeassistant.core

        return getattr(homeassistant.core, attr)

    return DeferredDeprecatedAlias(value_fn, f"homeassistant.core.{attr}", "2025.5")


# The following types should not used and
# are not present in the core code base.
# They are kept in order not to break custom integrations
# that may rely on them.
# Deprecated as of 2024.5 use types from homeassistant.core instead.
_DEPRECATED_ContextType = _deprecated_typing_helper("Context")
_DEPRECATED_EventType = _deprecated_typing_helper("Event")
_DEPRECATED_HomeAssistantType = _deprecated_typing_helper("HomeAssistant")
_DEPRECATED_ServiceCallType = _deprecated_typing_helper("ServiceCall")

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
