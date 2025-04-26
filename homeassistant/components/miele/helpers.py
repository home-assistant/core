"""Helpers for miele integration."""

from enum import IntEnum
import logging

_LOGGER = logging.getLogger(__name__)
completed_warnings: set[str] = set()


class MieleEnum(IntEnum):
    """Miele Enum for codes with int values."""

    @property
    def name(self) -> str:
        """Force to lower case."""
        return super().name.lower()

    @classmethod
    def _missing_(cls, value):
        if hasattr(cls, "unknown"):
            warning = f"Missing {cls.__name__} code: {value} - defaulting to 'unknown'"
            if warning not in completed_warnings:
                completed_warnings.add(warning)
                _LOGGER.warning(warning)
            return cls.unknown
        return None

    @classmethod
    def as_dict(cls):
        """Return a dict of enum names and values."""
        return {i.name: i.value for i in cls if i.name != "missing"}

    @classmethod
    def as_enum_dict(cls):
        """Return a dict of enum values and enum names."""
        return {i.value: i for i in cls if i.name != "missing"}

    @classmethod
    def values(cls) -> list[int]:
        """Return a list of enum values."""
        return list(cls.as_dict().values())

    @classmethod
    def keys(cls) -> list[str]:
        """Return a list of enum names."""
        return list(cls.as_dict().keys())

    @classmethod
    def items(cls):
        """Return a list of enum items."""
        return cls.as_dict().items()
