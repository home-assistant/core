"""Tests for the Snooz component."""
from __future__ import annotations

from pysnooz.testing import MockSnoozClient

from homeassistant.components.snooz.models import SnoozConfigurationData
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


def create_device_with_rssi(rssi: int) -> BluetoothServiceInfo:
    """Create a Snooz device with the specified signal strength."""

    return BluetoothServiceInfo(
        name=TEST_SNOOZ_LOCAL_NAME,
        address=TEST_ADDRESS,
        rssi=rssi,
        manufacturer_data={65552: bytes([4]) + bytes.fromhex(TEST_PAIRING_TOKEN)},
        service_uuids=[
            "80c37f00-cc16-11e4-8830-0800200c9a66",
            "90759319-1668-44da-9ef3-492d593bd1e5",
        ],
        service_data={},
        source="local",
    )


class SnoozFixture:
    """Snooz test fixture."""

    def __init__(
        self,
        entry: MockConfigEntry,
        client: MockSnoozClient,
        data: SnoozConfigurationData,
    ) -> None:
        """Initialize a Snooz fixture."""
        self.entry = entry
        self.client = client
        self.data = data
