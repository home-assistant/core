"""RFLink integration utils."""


def brightness_to_rflink(brightness: int) -> int:
    """Convert 0-255 brightness to RFLink dim level (0-15)."""
    return int(brightness / 17)


def rflink_to_brightness(dim_level: int) -> int:
    """Convert RFLink dim level (0-15) to 0-255 brightness."""
    return int(dim_level * 17)
