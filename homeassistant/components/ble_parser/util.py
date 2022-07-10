"""The BLE Parser integration."""
from __future__ import annotations

from struct import pack


def address_to_bytes(address: str) -> bytes:
    """Return the address as bytes."""
    if ":" not in address:
        address_as_int = 0
    else:
        address_as_int = int(address.replace(":", ""), 16)
    return pack("L", address_as_int)


def manufacturer_data_to_raw(manufacturer_id: int, manufacturer_data: bytes) -> bytes:
    """Return the raw data from manufacturer data."""
    return _pad_manufacturer_data(
        int(manufacturer_id).to_bytes(2, byteorder="little") + manufacturer_data
    )


def _pad_manufacturer_data(manufacturer_data: bytes) -> bytes:
    """Pad manufacturer data to the format bleparser needs."""
    return b"\x00" * 2 + manufacturer_data
