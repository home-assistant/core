"""Utilities for Rako."""


def create_unique_id(mac_address, room_id, channel_id) -> str:
    """Create Unique ID for light."""
    return f"b:{mac_address}r:{room_id}c:{channel_id}"
