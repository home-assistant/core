"""Implementation for EventType.

Custom for type checking. See stub file.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class EventType[_DataT: Mapping[str, Any] = Mapping[str, Any]](str):
    """Custom type for Event.event_type.

    At runtime this is a generic subclass of str.
    """

    __slots__ = ()
