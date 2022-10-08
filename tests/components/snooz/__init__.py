"""Tests for the Snooz component."""
from __future__ import annotations

from dataclasses import dataclass

from pysnooz.device import SnoozDevice
from pysnooz.testing import MockSnoozClient

from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry

TEST_ADDRESS = "00:00:00:00:AB:CD"
TEST_SNOOZ_LOCAL_NAME = "Snooz-ABCD"
TEST_SNOOZ_DISPLAY_NAME = "Snooz ABCD"
TEST_PAIRING_TOKEN = "deadbeef"

NOT_SNOOZ_SERVICE_INFO = BluetoothServiceInfo(
    name="Definitely not snooz",
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={3234: b"\x00\x01"},
    service_data={},
    service_uuids=[],
    source="local",
)

SNOOZ_SERVICE_INFO_PAIRING = BluetoothServiceInfo(
    name=TEST_SNOOZ_LOCAL_NAME,
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={65552: bytes([4]) + bytes.fromhex(TEST_PAIRING_TOKEN)},
    service_uuids=[
        "80c37f00-cc16-11e4-8830-0800200c9a66",
        "90759319-1668-44da-9ef3-492d593bd1e5",
    ],
    service_data={},
    source="local",
)

SNOOZ_SERVICE_INFO_NOT_PAIRING = BluetoothServiceInfo(
    name=TEST_SNOOZ_LOCAL_NAME,
    address=TEST_ADDRESS,
    rssi=-63,
    manufacturer_data={65552: bytes([4]) + bytes([0] * 8)},
    service_uuids=[
        "80c37f00-cc16-11e4-8830-0800200c9a66",
        "90759319-1668-44da-9ef3-492d593bd1e5",
    ],
    service_data={},
    source="local",
)


@dataclass
class SnoozFixture:
    """Snooz test fixture."""

    entry: MockConfigEntry
    client: MockSnoozClient
    device: SnoozDevice
