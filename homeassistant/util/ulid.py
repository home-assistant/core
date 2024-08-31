"""Helpers to generate ulids."""

from __future__ import annotations

from ulid_transform import (
    bytes_to_ulid,
    bytes_to_ulid_or_none,
    ulid_at_time,
    ulid_hex,
    ulid_now,
    ulid_to_bytes,
    ulid_to_bytes_or_none,
)

__all__ = [
    "ulid",
    "ulid_hex",
    "ulid_at_time",
    "ulid_to_bytes",
    "bytes_to_ulid",
    "ulid_now",
    "ulid_to_bytes_or_none",
    "bytes_to_ulid_or_none",
]


def ulid(timestamp: float | None = None) -> str:
    """Generate a ULID.

    This ulid should not be used for cryptographically secure
    operations.

     01AN4Z07BY      79KA1307SR9X4MV3
    |----------|    |----------------|
     Timestamp          Randomness
       48bits             80bits

    This string can be loaded directly with https://github.com/ahawker/ulid

    import homeassistant.util.ulid as ulid_util
    import ulid
    ulid.parse(ulid_util.ulid())
    """
    return ulid_now() if timestamp is None else ulid_at_time(timestamp)
