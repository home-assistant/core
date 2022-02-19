"""Helpers for Roku."""
from __future__ import annotations


def format_channel_name(channel_number: str, channel_name: str | None = None) -> str:
    """Format a Roku Channel name."""
    if channel_name is not None and channel_name != "":
        return f"{channel_name} ({channel_number})"

    return channel_number
