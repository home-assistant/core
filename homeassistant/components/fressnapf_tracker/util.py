"""Helpers for the Fressnapf Tracker integration."""

import hashlib


def hashed_serial_number(serialnumber: str) -> str:
    """Return a short hash of a serial number for repair issue IDs.

    Issue IDs are appended to diagnostics downloads without redaction,
    so the serial number itself must not be part of them.
    """
    return hashlib.sha256(serialnumber.encode()).hexdigest()[:16]
