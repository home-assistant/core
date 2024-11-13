"""Helpers for the Onkyo integration."""

from enum import Enum
from typing import ClassVar, Self


class EnumWithMeaning(Enum):
    """Enum with meaning."""

    __meaning_mapping: ClassVar[dict[str, Self]] = {}  # type: ignore[misc]

    value_meaning: str

    def __new__(cls, value: str) -> Self:
        """Create enum."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.value_meaning = cls._get_meanings()[value]

        cls.__meaning_mapping[obj.value_meaning] = obj

        return obj

    @staticmethod
    def _get_meanings() -> dict[str, str]:
        raise NotImplementedError

    @classmethod
    def from_meaning(cls, meaning: str) -> Self:
        """Get enum from its meaning."""
        return cls.__meaning_mapping[meaning]
