"""Test for initialization of ToGrill integration."""

from unittest.mock import Mock

from bleak.exc import BleakError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.togrill.const import (
    CONF_ACTIVE_BY_DEFAULT,
    DOMAIN,
    MAJOR_VERSION,
    MINOR_VERSION,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import TOGRILL_MOCK_ENTRY_DATA, TOGRILL_SERVICE_INFO, setup_entry

from tests.common import MockConfigEntry
from tests.components.bluetooth import inject_bluetooth_service_info


async def test_setup_device_present(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that setup works with device present."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    await setup_entry(hass, mock_entry, [])
    assert mock_entry.state is ConfigEntryState.LOADED

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_BLUETOOTH, TOGRILL_SERVICE_INFO.address)}
    )
    assert device == snapshot


async def test_setup_device_not_present(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
) -> None:
    """Test that setup succeeds if device is missing."""

    await setup_entry(hass, mock_entry, [])
    assert mock_entry.state is ConfigEntryState.LOADED


async def test_setup_device_failing(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
) -> None:
    """Test that setup fails if device is not responding."""

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)

    mock_client.is_connected = False
    mock_client.read.side_effect = BleakError("Failed to read data")

    await setup_entry(hass, mock_entry, [])
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY


async def test_migration_1_1(
    hass: HomeAssistant,
) -> None:
    """Test that setup succeeds if device is missing."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=TOGRILL_MOCK_ENTRY_DATA,
        options={},
        unique_id=TOGRILL_SERVICE_INFO.address,
        version=1,
        minor_version=1,
    )

    await setup_entry(hass, config_entry, [])
    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.version == MAJOR_VERSION
    assert config_entry.minor_version == MINOR_VERSION
    assert config_entry.options == {CONF_ACTIVE_BY_DEFAULT: True}
