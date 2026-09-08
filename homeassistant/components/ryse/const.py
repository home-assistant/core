"""Constants for the RYSE integration."""

from collections.abc import Mapping

DOMAIN = "ryse"
MANUFACTURER_NAME = "RYSE"
SERVICE_UUID = "a72f2800-b0bd-498b-b4cd-4a3901388238"
MANUFACTURER_ID = 1033
PAIRING_MODE_FLAG = 0x40


def is_pairing_mode(manufacturer_data: Mapping[int, bytes] | None) -> bool:
    """Return True if the shade is advertising that it accepts a new pairing."""
    if not manufacturer_data:
        return False
    payload = manufacturer_data.get(MANUFACTURER_ID)
    if not payload:
        return False
    return bool(payload[0] & PAIRING_MODE_FLAG)
