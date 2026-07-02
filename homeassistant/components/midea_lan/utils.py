"""Utils for Midea LAN."""

from midealocal.cloud import PRESET_ACCOUNT_DATA


def decode_preset_account(index: int) -> str:
    """Decode preset account data."""
    value = PRESET_ACCOUNT_DATA[0] ^ PRESET_ACCOUNT_DATA[index]
    hex_str = f"{value:x}"
    if len(hex_str) % 2:
        hex_str = "0" + hex_str
    return bytes.fromhex(hex_str).decode("utf-8", errors="ignore")
