"""Home Assistant state formatting."""

from vrchatapi.highlevel.presence import process_vrchat_string


def normalize_vrchat_enum_value(s: str | None = None):
    """Normalize a VRChat enum value for use as a Home Assistant state."""
    value = process_vrchat_string(s)
    return value.replace(" ", "_") if value is not None else None
