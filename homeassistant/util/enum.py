"""Utils for enums."""
from __future__ import annotations

from enum import EnumMeta


class StrEnumMeta(EnumMeta):
    """Use by StrEnum to match strings."""

    def __contains__(cls, member: object) -> bool:
        """Override to allow string comparison against the values."""
        if member is None:
            return False
        if isinstance(member, str):
            return member in cls._value2member_map_
        return super().__contains__(member)
