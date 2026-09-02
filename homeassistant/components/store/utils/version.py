"""Version utils."""

from __future__ import annotations

from functools import lru_cache

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)


@lru_cache(maxsize=1024)
def version_left_higher_then_right(left: str, right: str) -> bool | None:
    """Return a bool if source is newer than target, will also be true if identical."""
    try:
        left_version = AwesomeVersion(left)
        right_version = AwesomeVersion(right)
        if (
            left_version.strategy != AwesomeVersionStrategy.UNKNOWN
            and right_version.strategy != AwesomeVersionStrategy.UNKNOWN
        ):
            return left_version > right_version
    except (AwesomeVersionException, AttributeError, KeyError):
        pass

    return None


def version_left_higher_or_equal_then_right(left: str, right: str) -> bool:
    """Return a bool if source is newer than target, will also be true if identical."""
    if left == right:
        return True

    return version_left_higher_then_right(left, right)
