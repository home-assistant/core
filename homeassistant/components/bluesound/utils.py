"""Utility functions for the Bluesound component."""

from homeassistant.helpers.device_registry import format_mac


def format_unique_id(mac: str, port: int) -> str:
    """Generate a unique ID based on the MAC address and port number."""
    return f"{format_mac(mac)}-{port}"
