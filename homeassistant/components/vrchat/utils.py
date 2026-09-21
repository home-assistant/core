"""Home Assistant state and image formatting."""

import base64

from vrchatapi.highlevel.presence import process_vrchat_string


def normalize_vrchat_enum_value(s: str | None = None):
    """Normalize a VRChat enum value for use as a Home Assistant state."""
    value = process_vrchat_string(s)
    return value.replace(" ", "_") if value is not None else None


def svg_file_uri(svg: str):
    """Turn an SVG string into a data URI."""
    return f"data:image/svg+xml;charset=utf-8;base64,{base64.b64encode(svg.encode()).decode('ascii')}"
