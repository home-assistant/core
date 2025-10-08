"""Models for Recorder."""

from __future__ import annotations

from contextlib import suppress
from functools import lru_cache
import logging
from uuid import UUID

from homeassistant.util.ulid import (  # noqa: F401
    bytes_to_ulid,
    bytes_to_ulid_or_none,
    ulid_to_bytes,
    ulid_to_bytes_or_none,
)

_LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=16)
def uuid_hex_to_bytes_or_none(uuid_hex: str | None) -> bytes | None:
    """Convert a uuid hex to bytes."""
    if uuid_hex is None:
        return None
    with suppress(ValueError):
        return UUID(hex=uuid_hex).bytes
    return None


@lru_cache(maxsize=16)
def bytes_to_uuid_hex_or_none(_bytes: bytes | None) -> str | None:
    """Convert bytes to a uuid hex."""
    if _bytes is None:
        return None
    with suppress(ValueError):
        return UUID(bytes=_bytes).hex
    return None
