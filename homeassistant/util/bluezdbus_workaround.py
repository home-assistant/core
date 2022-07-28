"""Workaround for bleak executing a subprocess on import."""

# These values are defaults and will be replaced
# with the actual values when the bluetooth integration
# is loaded.
BLUEZ_MAJOR = 5
BLUEZ_MINOR = 51


def check_bluez_version(major: int, minor: int) -> bool:
    """Check if the version of bluez is new enough."""
    return BLUEZ_MAJOR == major and BLUEZ_MINOR >= minor
