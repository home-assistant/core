"""RFLink integration utils."""

from .const import EVENT_KEY_COMMAND, EVENT_KEY_SENSOR


def brightness_to_rflink(brightness: int) -> int:
    """Convert 0-255 brightness to RFLink dim level (0-15)."""
    return int(brightness / 17)


def rflink_to_brightness(dim_level: int) -> int:
    """Convert RFLink dim level (0-15) to 0-255 brightness."""
    return int(dim_level * 17)


def identify_event_type(event):
    """Look at event to determine type of device.

    Async friendly.
    """
    if EVENT_KEY_COMMAND in event:
        return EVENT_KEY_COMMAND
    if EVENT_KEY_SENSOR in event:
        return EVENT_KEY_SENSOR
    return "unknown"
