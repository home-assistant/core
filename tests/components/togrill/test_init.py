"""Test for initialization of ToGrill integration."""

from unittest.mock import Mock

from bleak.exc import BleakError
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.togrill.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import TOGRILL_SERVICE_INFO, setup_entry


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

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_BLUETOOTH, TOGRILL_SERVICE_INFO.address), mock_entry.entry_id
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


async def test_migrate_probe_to_child_device(
    hass: HomeAssistant,
    mock_entry: MockConfigEntry,
    mock_client: Mock,
    mock_client_class: Mock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that an existing probe device is converted to a child device in place."""
    mock_entry.add_to_hass(hass)
    parent = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, TOGRILL_SERVICE_INFO.address)},
    )
    probe = device_registry.async_get_or_create(
        config_entry_id=mock_entry.entry_id,
        identifiers={(DOMAIN, f"{TOGRILL_SERVICE_INFO.address}_1")},
        via_device_id=parent.id,
    )
    # Devices registered before a restart are not live for the new setup.
    device_registry.async_config_entry_unloaded(mock_entry.entry_id)

    inject_bluetooth_service_info(hass, TOGRILL_SERVICE_INFO)
    await setup_entry(hass, mock_entry, [Platform.SENSOR])
    assert mock_entry.state is ConfigEntryState.LOADED

    child = device_registry.async_get_child_device_by_identifier(
        (DOMAIN, f"{TOGRILL_SERVICE_INFO.address}_1"), mock_entry.entry_id
    )
    assert child is not None
    assert child.id == probe.id
    assert child.parent_device_id == parent.id
