"""Constants and helpers for the KlikAanKlikUit (Kaku) integration."""

from typing import Final

DOMAIN: Final = "klik_aan_klik_uit"

CONF_TRANSMITTER: Final = "transmitter"
CONF_CHANNEL: Final = "channel"
CONF_GROUP: Final = "group"
CONF_DIM: Final = "dim"
REPEAT_COUNT_LEARN: Final = 10  # Higher repeats for learning/pairing


def format_device_summary(device_id: int, channel: int, group: bool, dim: bool) -> str:
    """Return a concise summary string for the configured device."""
    group_text = "on" if group else "off"
    dim_text = "on" if dim else "off"
    return f"ID {device_id} CH {channel} Group {group_text} Brightness {dim_text}"
