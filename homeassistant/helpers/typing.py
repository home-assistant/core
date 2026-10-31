"""Typing Helpers for Home Assistant."""

from collections.abc import Mapping
from functools import partial
from typing import TYPE_CHECKING, Any, Never

import probatio

# 'typing_extensions.sentinel' is not supported by Pylance yet, requires >2026.4.1
# Use temporary alias to make the switch easier later.
from typing_extensions import Sentinel as sentinel

from .deprecation import (
    DeprecatedAlias,
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
type VolSchemaType = probatio.Schema | probatio.All | probatio.Any | probatio.Union
type VolDictType = dict[str | probatio.Marker, Any]

# Custom type for recorder Queries
type QueryType = Any

Undefined = sentinel("Undefined")
_DEPRECATED_UNDEFINED = DeprecatedAlias(
    Undefined, "homeassistant.helpers.typing.Undefined", "2027.12"
)
_DEPRECATED_UndefinedType = DeprecatedAlias(
    Undefined, "homeassistant.helpers.typing.Undefined", "2027.12"
)

if TYPE_CHECKING:
    # Add typing aliases for backwards compatibility
    UNDEFINED = Undefined
    UndefinedType = Undefined

# These can be removed if no deprecated constants are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
