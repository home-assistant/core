"""Decode a BLE GAP AD structure from a shelly."""

# This needs to be moved to the aioshelly lib

import base64
from collections.abc import Iterable
from enum import IntEnum


class BLEGAPType(IntEnum):
    """Advertising data types."""

    TYPE_FLAGS = 0x01
    TYPE_16BIT_SERVICE_UUID_MORE_AVAILABLE = 0x02
    TYPE_16BIT_SERVICE_UUID_COMPLETE = 0x03
    TYPE_32BIT_SERVICE_UUID_MORE_AVAILABLE = 0x04
    TYPE_32BIT_SERVICE_UUID_COMPLETE = 0x05
    TYPE_128BIT_SERVICE_UUID_MORE_AVAILABLE = 0x06
    TYPE_128BIT_SERVICE_UUID_COMPLETE = 0x07
    TYPE_SHORT_LOCAL_NAME = 0x08
    TYPE_COMPLETE_LOCAL_NAME = 0x09
    TYPE_TX_POWER_LEVEL = 0x0A
    TYPE_CLASS_OF_DEVICE = 0x0D
    TYPE_SIMPLE_PAIRING_HASH_C = 0x0E
    TYPE_SIMPLE_PAIRING_RANDOMIZER_R = 0x0F
    TYPE_SECURITY_MANAGER_TK_VALUE = 0x10
    TYPE_SECURITY_MANAGER_OOB_FLAGS = 0x11
    TYPE_SLAVE_CONNECTION_INTERVAL_RANGE = 0x12
    TYPE_SOLICITED_SERVICE_UUIDS_16BIT = 0x14
    TYPE_SOLICITED_SERVICE_UUIDS_128BIT = 0x15
    TYPE_SERVICE_DATA = 0x16
    TYPE_PUBLIC_TARGET_ADDRESS = 0x17
    TYPE_RANDOM_TARGET_ADDRESS = 0x18
    TYPE_APPEARANCE = 0x19
    TYPE_ADVERTISING_INTERVAL = 0x1A
    TYPE_LE_BLUETOOTH_DEVICE_ADDRESS = 0x1B
    TYPE_LE_ROLE = 0x1C
    TYPE_SIMPLE_PAIRING_HASH_C256 = 0x1D
    TYPE_SIMPLE_PAIRING_RANDOMIZER_R256 = 0x1E
    TYPE_SERVICE_DATA_32BIT_UUID = 0x20
    TYPE_SERVICE_DATA_128BIT_UUID = 0x21
    TYPE_URI = 0x24
    TYPE_3D_INFORMATION_DATA = 0x3D
    TYPE_MANUFACTURER_SPECIFIC_DATA = 0xFF


BLEGAPType_MAP = {gap_ad.value: gap_ad for gap_ad in BLEGAPType}


def decode_ad(encoded_struct: bytes) -> Iterable[tuple[BLEGAPType, bytes]]:
    """Decode a BLE GAP AD structure."""
    offset = 0
    while offset < len(encoded_struct):
        length = encoded_struct[offset]
        type_ = encoded_struct[offset + 1]
        value = encoded_struct[offset + 2 :][: length - 1]
        yield BLEGAPType_MAP[type_], value
        offset += 1 + length


def test_decoder() -> None:
    """Test the decoder."""
    msg = "AgEGFv9MAAYxAIK3JI37ygoAShYBAkUeEkQECE9udg=="
    msg = "Dhbw/zYCFrLcDRU2zclkAwL1/gsJRlNDLUJQMTA1Tg=="
    raw = base64.b64decode(msg)
    import pprint  # pylint: disable=import-outside-toplevel

    pprint.pprint(raw)
    pprint.pprint(list(decode_ad(raw)))


test_decoder()
