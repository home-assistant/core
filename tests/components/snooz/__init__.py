"""Tests for the Snooz component."""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch
from pysnooz import (
    SnoozAdvertisementData,
    SnoozDeviceModel,
    SnoozFirmwareVersion,
    SnoozDeviceState,
)

from pysnooz.testing import MockSnoozDevice

from homeassistant.components.snooz.const import CONF_FIRMWARE_VERSION, DOMAIN
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device

TEST_ADDRESS = "00:00:00:00:AB:CD"
TEST_SNOOZ_LOCAL_NAME = "Snooz-ABCD"
TEST_SNOOZ_DISPLAY_NAME = "Snooz ABCD"
TEST_SNOOZ_MODEL = SnoozDeviceModel.ORIGINAL
TEST_SNOOZ_FIRMWARE_VERSION = SnoozFirmwareVersion.V2
TEST_PAIRING_TOKEN = "deadbeefdeadbeef"

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
    manufacturer_data={0xFFFF: bytes([0x05]) + bytes.fromhex(TEST_PAIRING_TOKEN)},
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
    manufacturer_data={0xFFFF: bytes([0x04]) + bytes([0] * 8)},
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


async def create_mock_snooz(
    connected: bool = True,
    initial_state: SnoozDeviceState = SnoozDeviceState(on=False, volume=0),
    model: SnoozDeviceModel = TEST_SNOOZ_MODEL,
    firmware_version: SnoozFirmwareVersion = TEST_SNOOZ_FIRMWARE_VERSION,
) -> MockSnoozDevice:
    """Create a mock device."""

    adv_data = SnoozAdvertisementData(model, firmware_version, TEST_PAIRING_TOKEN)
    device = MockSnoozDevice(
        generate_ble_device(address=TEST_ADDRESS, name=TEST_SNOOZ_LOCAL_NAME),
        adv_data,
        initial_state=initial_state,
    )

    if not connected:
        device.trigger_disconnect()

    return device


async def create_mock_snooz_config_entry(
    hass: HomeAssistant, device: MockSnoozDevice, version=2
) -> MockConfigEntry:
    """Create a mock config entry."""

    with patch(
        "homeassistant.components.snooz.SnoozDevice", return_value=device
    ), patch(
        "homeassistant.components.snooz.async_ble_device_from_address",
        return_value=generate_ble_device(device.address, device.name),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=version,
            unique_id=TEST_ADDRESS,
            data={
                CONF_ADDRESS: device.address,
                CONF_TOKEN: TEST_PAIRING_TOKEN,
                CONF_MODEL: device.model,
                CONF_FIRMWARE_VERSION: device.firmware_version,
            },
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        return entry
