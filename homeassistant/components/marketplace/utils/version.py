"""Version utils."""

from functools import lru_cache

from awesomeversion import (
    AwesomeVersion,
    AwesomeVersionException,
    AwesomeVersionStrategy,
)


@lru_cache(maxsize=1024)
def is_newer_version(left: str, right: str) -> bool | None:
    """Return if left is newer than right, None when they can not be compared."""
    try:
        left_version = AwesomeVersion(left)
        right_version = AwesomeVersion(right)
        if AwesomeVersionStrategy.UNKNOWN not in (
            left_version.strategy,
            right_version.strategy,
        ):
            return left_version > right_version
    except AwesomeVersionException, AttributeError, KeyError:
        pass

    return None


def is_same_or_newer_version(left: str, right: str) -> bool:
    """Return if left is the same as or newer than right."""
    if left == right:
        return True

    return is_newer_version(left, right) or False
