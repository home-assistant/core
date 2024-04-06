"""Implementation for EventType."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Generic

from typing_extensions import TypeVar

_DataT = TypeVar("_DataT", bound=Mapping[str, Any], default=Mapping[str, Any])


if TYPE_CHECKING:

    class EventType(Generic[_DataT]):
        """Custom type for Event.event_type.

        For type checkers pretend to its own separate class.
        """

        def __init__(self, value: str, /) -> None:
            """Stub. At runtime delegated to str."""

        def __len__(self) -> int:
            """Stub. At runtime delegated to str."""

        def __hash__(self) -> int:
            """Stub. At runtime delegated to str."""

        def __eq__(self, value: object, /) -> bool:
            """Stub. At runtime delegated to str."""

        def __getitem__(self, index: int) -> str:
            """Stub. At runtime delegated to str."""

else:

    class EventType(str, Generic[_DataT]):
        """Custom type for Event.event_type.

        At runtime this is a generic subclass of str.
        """
