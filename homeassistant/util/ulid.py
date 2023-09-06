"""Helpers to generate ulids."""
from __future__ import annotations

import time

from ulid_transform import bytes_to_ulid, ulid_at_time, ulid_hex, ulid_to_bytes

__all__ = ["ulid", "ulid_hex", "ulid_at_time", "ulid_to_bytes", "bytes_to_ulid"]


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
    return ulid_at_time(timestamp or time.time())
