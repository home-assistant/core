"""Tests for the Snooz component."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

from pysnooz.commands import SnoozCommandData
from pysnooz.device import DisconnectionReason
from pysnooz.testing import MockSnoozDevice as ParentMockSnoozDevice

from homeassistant.components.snooz.const import DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

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
    device: MockSnoozDevice


class MockSnoozDevice(ParentMockSnoozDevice):
    """Used for testing integration with Bleak.

    Adjusted for https://github.com/AustinBrunkhorst/pysnooz/issues/6
    """

    def _on_device_disconnected(self, e) -> None:
        if self._is_manually_disconnecting:
            e.kwargs.set("reason", DisconnectionReason.USER)
        return super()._on_device_disconnected(e)


async def create_mock_snooz(
    connected: bool = True,
    initial_state: SnoozCommandData = SnoozCommandData(on=False, volume=0),
) -> MockSnoozDevice:
    """Create a mock device."""

    ble_device = SNOOZ_SERVICE_INFO_NOT_PAIRING
    device = MockSnoozDevice(ble_device, initial_state=initial_state)

    # execute a command to initiate the connection
    if connected is True:
        await device.async_execute_command(initial_state)

    return device


async def create_mock_snooz_config_entry(
    hass: HomeAssistant, device: MockSnoozDevice
) -> MockConfigEntry:
    """Create a mock config entry."""

    with (
        patch("homeassistant.components.snooz.SnoozDevice", return_value=device),
        patch(
            "homeassistant.components.snooz.async_ble_device_from_address",
            return_value=generate_ble_device(device.address, device.name),
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=TEST_ADDRESS,
            data={CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN},
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry
