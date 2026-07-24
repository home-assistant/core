"""Identity helpers for the Elke27 integration."""

import re

from .const import MANUFACTURER_NUMBER

_CLIENT_ID_RE = re.compile(r"[^a-z0-9]")


def normalize_identifier(value: str) -> str:
    """Normalize a value to lowercase ASCII alphanumeric characters."""
    return _CLIENT_ID_RE.sub("", value.lower())


def derive_client_id(entry_id: str) -> str:
    """Return the Elk client ID for this Home Assistant config entry."""
    return normalize_identifier(entry_id)


def build_client_identity(client_id: str) -> dict[str, str]:
    """Return the client identity mapping for provisioning and session setup."""
    return {
        "mn": str(MANUFACTURER_NUMBER),
        "sn": client_id,
    }
