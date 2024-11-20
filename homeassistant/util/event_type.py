"""Implementation for EventType.

Custom for type checking. See stub file.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Generic

from typing_extensions import TypeVar

_DataT = TypeVar("_DataT", bound=Mapping[str, Any], default=Mapping[str, Any])


class EventType(str, Generic[_DataT]):
    """Custom type for Event.event_type.

    At runtime this is a generic subclass of str.
    """

    __slots__ = ()
