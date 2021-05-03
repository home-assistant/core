"""Utilities for Rako."""
from __future__ import annotations

import hashlib
from typing import Any


def create_unique_id(bridge_id: str, room_id: int, channel_id: int) -> str:
    """Create Unique ID for light."""
    return f"b:{bridge_id}r:{room_id}c:{channel_id}"


def hash_dict(input_dict: dict[str, Any]) -> str:
    """Hashes a dict."""
    info_hash = hashlib.blake2s(digest_size=5)
    for key, val in sorted(input_dict.items()):
        info_hash.update(str(key).encode())
        info_hash.update(str(val).encode())

    return info_hash.hexdigest()
