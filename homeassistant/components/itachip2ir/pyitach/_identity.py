"""iTach identity helpers."""

from ._discovery import normalize_uuid


def normalize_device_id(value: str | None) -> str | None:
    """Normalize an iTach device id into GlobalCache_XXXXXXXXXXXX.

    Accepts GlobalCache_XXXXXXXXXXXX, raw 12-character ids, and MAC-style
    colon/dash-separated values. The canonical config-entry identity is the
    Global Caché UUID.
    """
    if value is None or not value.strip():
        return None
    return normalize_uuid(value)
