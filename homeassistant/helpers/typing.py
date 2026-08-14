"""Typing Helpers for Home Assistant."""

from collections.abc import Mapping
from enum import Enum
from typing import Any, Never

import voluptuous as vol

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
