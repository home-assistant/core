"""Stub file for event_type. Provide overload for type checking."""
# ruff: noqa: PYI021  # Allow docstrings

from collections.abc import Mapping
from typing import Any, Generic, TypeVar

__all__ = [
    "EventType",
]

_DataT = TypeVar(  # needs to be invariant
    "_DataT", bound=Mapping[str, Any], default=Mapping[str, Any]
)

class EventType(Generic[_DataT]):
    """Custom type for Event.event_type. At runtime delegated to str.

    For type checkers pretend to be its own separate class.
    """

    def __init__(self, value: str, /) -> None: ...
    def __len__(self) -> int: ...
    def __hash__(self) -> int: ...
    def __eq__(self, value: object, /) -> bool: ...
    def __getitem__(self, index: int) -> str: ...
