"""Decode a BLE GAP AD structure from a shelly."""

from __future__ import annotations

# This needs to be moved to the aioshelly lib
from base64 import b64decode
from collections.abc import Iterable
from enum import IntEnum
from uuid import UUID

BLE_UUID = "0000-1000-8000-00805f9b34fb"


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


def parse_ble_event(
    advertisement_data_b64: str, scan_response_b64: str
) -> tuple[str | None, dict[int, bytes], dict[str, bytes], list[str]]:
    """Convert ad data to BLEDevice and AdvertisementData."""
    manufacturer_data: dict[int, bytes] = {}
    service_data: dict[str, bytes] = {}
    service_uuids: list[str] = []
    local_name: str | None = None

    for gap_data in advertisement_data_b64, scan_response_b64:
        gap_data_byte = b64decode(gap_data)
        for gap_type, gap_value in decode_ad(gap_data_byte):
            if gap_type == BLEGAPType.TYPE_SHORT_LOCAL_NAME and not local_name:
                local_name = gap_value.decode("utf-8")
            elif gap_type == BLEGAPType.TYPE_COMPLETE_LOCAL_NAME:
                local_name = gap_value.decode("utf-8")
            elif gap_type == BLEGAPType.TYPE_MANUFACTURER_SPECIFIC_DATA:
                manufacturer_id = int.from_bytes(gap_value[:2], "little")
                manufacturer_data[manufacturer_id] = gap_value[2:]
            elif gap_type in {
                BLEGAPType.TYPE_16BIT_SERVICE_UUID_COMPLETE,
                BLEGAPType.TYPE_16BIT_SERVICE_UUID_MORE_AVAILABLE,
            }:
                service_uuids.append(f"0000{gap_value.hex()}-{BLE_UUID}")
            elif gap_type in {
                BLEGAPType.TYPE_128BIT_SERVICE_UUID_MORE_AVAILABLE,
                BLEGAPType.TYPE_128BIT_SERVICE_UUID_COMPLETE,
            }:
                service_uuids.append(f"{gap_value.hex()}-{BLE_UUID}")
            elif gap_type == BLEGAPType.TYPE_SERVICE_DATA:
                service_data[f"0000{gap_value[:2].hex()}-{BLE_UUID}"] = gap_value[2:]
            elif gap_type == BLEGAPType.TYPE_SERVICE_DATA_32BIT_UUID:
                service_data[f"{gap_value[:4].hex()}-{BLE_UUID}"] = gap_value[4:]
            elif gap_type == BLEGAPType.TYPE_SERVICE_DATA_128BIT_UUID:
                service_data[str(UUID(bytes=gap_value[:16]))] = gap_value[16:]

    return local_name, manufacturer_data, service_data, service_uuids
