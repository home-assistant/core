"""Utility functions for the Bluesound component."""

from homeassistant.helpers.device_registry import format_mac


def format_unique_id(mac: str, port: int) -> str:
    """Generate a unique ID based on the MAC address and port number."""
    return f"{format_mac(mac)}-{port}"


def dispatcher_join_signal(entity_id: str) -> str:
    """Join an entity ID with a signal."""
    return f"bluesound_join_{entity_id}"


def dispatcher_unjoin_signal(leader_id: str) -> str:
    """Unjoin an entity ID with a signal.

    Id is ip_address:port. This can be obtained from sync_status.id.
    """
    return f"bluesound_unjoin_{leader_id}"
