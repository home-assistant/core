"""Utilities for Rako."""
import hashlib
from typing import Dict


def create_unique_id(bridge_id, room_id, channel_id) -> str:
    """Create Unique ID for light."""
    return f"b:{bridge_id}r:{room_id}c:{channel_id}"


def hash_dict(d: Dict) -> str:
    """Hashes a dict."""
    info_hash = hashlib.blake2s(digest_size=5)
    for k, v in sorted(d.items()):
        info_hash.update(str(k).encode())
        info_hash.update(str(v).encode())

    return info_hash.hexdigest()
