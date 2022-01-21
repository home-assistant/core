"""Enum backports from standard lib."""
from __future__ import annotations

from enum import Enum, EnumMeta
from typing import Any, TypeVar

T = TypeVar("T", bound="StrEnum")


class StrEnumMeta(EnumMeta):
    """Use by StrEnum to match strings."""

    def __contains__(cls, member: object) -> bool:
        """Override to allow string comparison."""
        if isinstance(member, str):
            return member in cls._value2member_map_
        return super().__contains__(member)


class StrEnum(str, Enum, metaclass=StrEnumMeta):
    """Partial backport of Python 3.11's StrEnum for our basic use cases."""

    def __new__(cls: type[T], value: str, *args: Any, **kwargs: Any) -> T:
        """Create a new StrEnum instance."""
        if not isinstance(value, str):
            raise TypeError(f"{value!r} is not a string")
        return super().__new__(cls, value, *args, **kwargs)

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)

    @staticmethod
    def _generate_next_value_(  # pylint: disable=arguments-differ # https://github.com/PyCQA/pylint/issues/5371
        name: str, start: int, count: int, last_values: list[Any]
    ) -> Any:
        """
        Make `auto()` explicitly unsupported.

        We may revisit this when it's very clear that Python 3.11's
        `StrEnum.auto()` behavior will no longer change.
        """
        raise TypeError("auto() is not supported by this implementation")
