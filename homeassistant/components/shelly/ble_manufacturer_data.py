"""Bluetooth support for Shelly integration."""

from __future__ import annotations

import logging

_LOGGER = logging.getLogger(__name__)

ALLTERCO_MFID = 0x0BA9

# Block types in manufacturer data
BLOCK_TYPE_FLAGS = 0x01
BLOCK_TYPE_MAC = 0x0A
BLOCK_TYPE_MODEL = 0x0B

# Shelly bitfield flags (block type 0x01)
FLAG_DISCOVERABLE = 1 << 0
FLAG_AUTH_ENABLED = 1 << 1
FLAG_RPC_OVER_BLE_ENABLED = 1 << 2
FLAG_BUZZER_ENABLED = 1 << 3
FLAG_IN_PAIRING_MODE = 1 << 4


def parse_shelly_manufacturer_data(
    manufacturer_data: dict[int, bytes],
) -> dict[str, int | str] | None:
    """Parse Shelly manufacturer data from BLE advertisement.

    Args:
        manufacturer_data: Manufacturer data from BLE advertisement

    Returns:
        Dict with parsed data (flags, mac, model) or None if invalid

    """
    if ALLTERCO_MFID not in manufacturer_data:
        return None

    data = manufacturer_data[ALLTERCO_MFID]
    if len(data) < 1:
        return None

    result: dict[str, int | str] = {}
    offset = 0

    # Parse blocks
    while offset < len(data):
        if offset + 1 > len(data):
            break

        block_type = data[offset]
        offset += 1

        if block_type == BLOCK_TYPE_FLAGS:
            # 2 bytes of flags
            if offset + 2 > len(data):
                break
            flags = int.from_bytes(data[offset : offset + 2], byteorder="little")
            result["flags"] = flags
            offset += 2

        elif block_type == BLOCK_TYPE_MAC:
            # 6 bytes MAC address
            if offset + 6 > len(data):
                break
            mac_bytes = data[offset : offset + 6]
            # Format as standard MAC address
            result["mac"] = ":".join(f"{b:02X}" for b in mac_bytes)
            offset += 6

        elif block_type == BLOCK_TYPE_MODEL:
            # 2 bytes model ID
            if offset + 2 > len(data):
                break
            model_id = int.from_bytes(data[offset : offset + 2], byteorder="little")
            result["model_id"] = model_id
            offset += 2

        else:
            # Unknown block type - can't continue parsing
            _LOGGER.debug("Unknown block type in manufacturer data: 0x%02X", block_type)
            break

    return result if result else None


def has_rpc_over_ble(manufacturer_data: dict[int, bytes]) -> bool:
    """Check if device has RPC-over-BLE enabled.

    Args:
        manufacturer_data: Manufacturer data from BLE advertisement

    Returns:
        True if RPC-over-BLE is enabled

    """
    parsed = parse_shelly_manufacturer_data(manufacturer_data)
    if not parsed or "flags" not in parsed:
        return False

    flags = parsed["flags"]
    if not isinstance(flags, int):
        return False

    return bool(flags & FLAG_RPC_OVER_BLE_ENABLED)
