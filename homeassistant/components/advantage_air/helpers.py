"""Helpers for Advantage Air."""

from typing import Any


def get_system_id(system: dict[str, Any]) -> str:
    """Return the system rid, or the mid when the tablet reports no rid.

    Tablets that never registered with Advantage Air remote access have no rid.
    """
    return system.get("rid") or system["mid"]
