"""Test Snooz configuration."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.snooz.const import CONF_FIRMWARE_VERSION, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_MODEL, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from . import (
    SNOOZ_SERVICE_INFO_CHARACTERISTIC_NAME,
    SNOOZ_SERVICE_INFO_NOT_PAIRING,
    TEST_ADDRESS,
    TEST_FIRMWARE_VERSION,
    TEST_MODEL,
    TEST_PAIRING_TOKEN,
    SnoozFixture,
    create_mock_snooz,
)

TEST_ENTRY_DATA = {
    CONF_ADDRESS: TEST_ADDRESS,
    CONF_TOKEN: TEST_PAIRING_TOKEN,
    CONF_MODEL: TEST_MODEL,
    CONF_FIRMWARE_VERSION: TEST_FIRMWARE_VERSION,
}
# entries created before minor version 2 only stored the address and token
TEST_ENTRY_DATA_V1_1 = {CONF_ADDRESS: TEST_ADDRESS, CONF_TOKEN: TEST_PAIRING_TOKEN}


async def test_setup_retries_when_ble_device_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup is retried when the device is not available over Bluetooth."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_ADDRESS, minor_version=2, data=TEST_ENTRY_DATA
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snooz.async_ble_device_from_address",
            return_value=None,
        ) as mock_ble_device_from_address,
        patch(
            "homeassistant.components.snooz.async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_ble_device_from_address.assert_called_once_with(hass, TEST_ADDRESS)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        f"Could not find Snooz with address {TEST_ADDRESS}: mock reachability reason"
        in caplog.text
    )


async def test_setup_uses_stored_model_and_firmware_version(
    hass: HomeAssistant,
) -> None:
    """Test setup builds the device from the entry without parsing an advertisement."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_ADDRESS, minor_version=2, data=TEST_ENTRY_DATA
    )
    entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, SNOOZ_SERVICE_INFO_NOT_PAIRING)

    device = await create_mock_snooz()
    with (
        patch(
            "homeassistant.components.snooz.parse_snooz_advertisement",
            return_value=None,
        ),
        patch(
            "homeassistant.components.snooz.SnoozDevice", return_value=device
        ) as mock_snooz_device,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    advertisement = mock_snooz_device.call_args.args[1]
    assert advertisement.model == TEST_MODEL
    assert advertisement.firmware_version == TEST_FIRMWARE_VERSION
    assert advertisement.password == TEST_PAIRING_TOKEN


@pytest.mark.parametrize(
    "service_info",
    [SNOOZ_SERVICE_INFO_NOT_PAIRING, SNOOZ_SERVICE_INFO_CHARACTERISTIC_NAME],
    ids=["advertised_name", "characteristic_name"],
)
async def test_migrate_entry_stores_model_and_firmware_version(
    hass: HomeAssistant, service_info: BluetoothServiceInfo
) -> None:
    """Test a 1.1 entry is migrated from the cached advertisement."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_ADDRESS, data=TEST_ENTRY_DATA_V1_1
    )
    entry.add_to_hass(hass)
    inject_bluetooth_service_info(hass, service_info)

    device = await create_mock_snooz()
    with patch("homeassistant.components.snooz.SnoozDevice", return_value=device):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == TEST_ENTRY_DATA


async def test_migrate_entry_retries_when_service_info_not_found(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration of a 1.1 entry is retried until an advertisement is cached."""
    entry = MockConfigEntry(
        domain=DOMAIN, unique_id=TEST_ADDRESS, data=TEST_ENTRY_DATA_V1_1
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snooz.async_last_service_info",
            return_value=None,
        ) as mock_last_service_info,
        patch(
            "homeassistant.components.snooz.async_address_reachability_diagnostics",
            return_value="mock reachability reason",
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_last_service_info.assert_called_once_with(hass, TEST_ADDRESS)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert entry.minor_version == 1
    assert entry.data == TEST_ENTRY_DATA_V1_1
    assert (
        f"Could not find Snooz with address {TEST_ADDRESS}: mock reachability reason"
        in caplog.text
    )


async def test_device_registry(
    hass: HomeAssistant,
    mock_connected_snooz: SnoozFixture,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the Bluetooth connection."""
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_ADDRESS), mock_connected_snooz.entry.entry_id
    )
    assert device_entry == snapshot


async def test_removing_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Tests setup and removal of a config entry, cleaning up connections."""
    await hass.config_entries.async_remove(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected


async def test_reloading_entry_cleans_up_connections(
    hass: HomeAssistant, mock_connected_snooz: SnoozFixture
) -> None:
    """Test reloading an entry disconnects any existing connections."""
    await hass.config_entries.async_reload(mock_connected_snooz.entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_connected_snooz.device.is_connected
