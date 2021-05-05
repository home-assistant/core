"""Utilities for Rako."""
from __future__ import annotations


def create_unique_id(bridge_id: str, room_id: int, channel_id: int) -> str:
    """Create Unique ID for light."""
    return f"b:{bridge_id}r:{room_id}c:{channel_id}"
