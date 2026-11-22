"""Constants and helpers for the Intertechno TriState integration."""

from typing import Final

DOMAIN: Final = "intertechno_tristate"

CONF_TRANSMITTER: Final = "transmitter"
CONF_HOUSECODE: Final = "housecode"
CONF_CHANNEL: Final = "channel"
CONF_GROUP: Final = "group"
REPEAT_COUNT_LEARN: Final = 10


def format_device_summary(housecode: str, group: int, channel: int) -> str:
    """Return a concise summary string for the configured device."""
    return f"HC {housecode} G {group} CH {channel}"