"""Tests for the EARN-E P1 Meter integration setup."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.earn_e_p1.const import CONF_SERIAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import DOMAIN, MOCK_MAC, MOCK_NEW_HOST, MOCK_SERIAL, trigger_callback

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test successful setup of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()
    mock_listener.register.assert_called_once()


async def test_setup_entry_oserror_raises_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test that OSError during setup raises ConfigEntryNotReady."""
    mock_listener.start = AsyncMock(side_effect=OSError("Address in use"))

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test unloading a config entry stops the shared listener."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.unregister.assert_called()
    mock_listener.stop.assert_awaited()


async def test_unload_entry_keeps_listener_for_other_loaded_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_listener: MagicMock
) -> None:
    """Test the shared listener is only stopped when the last entry unloads."""
    other_serial = "E0098765432109876"
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"EARN-E P1 ({MOCK_NEW_HOST})",
        data={CONF_HOST: MOCK_NEW_HOST, CONF_SERIAL: other_serial},
        unique_id=other_serial,
    )
    other_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert other_entry.state is ConfigEntryState.LOADED
    mock_listener.start.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.stop.assert_not_awaited()

    await hass.config_entries.async_unload(other_entry.entry_id)
    await hass.async_block_till_done()

    assert other_entry.state is ConfigEntryState.NOT_LOADED
    mock_listener.stop.assert_awaited_once()


async def test_device_info(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test device info is correctly populated."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize("mock_config_entry", [{CONF_MAC: MOCK_MAC}], indirect=True)
async def test_device_info_with_mac(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test MAC is added to device connections when stored in entry data."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:11:22:33") in device.connections


async def test_device_registry_not_updated_on_identical_callback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is not updated when model/sw_version are unchanged."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    first_modified = device.modified_at

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.modified_at == first_modified


async def test_device_registry_updated_on_sw_version_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_listener: MagicMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is updated when sw_version changes."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    trigger_callback(mock_listener)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "1.0.0"

    trigger_callback(mock_listener, sw_version="2.0.0")
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, MOCK_SERIAL), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "2.0.0"
