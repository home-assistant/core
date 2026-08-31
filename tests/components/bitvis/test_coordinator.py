"""Tests for the Bitvis Power Hub coordinator."""

from unittest.mock import AsyncMock, MagicMock

from bitvis_protobuf.listener import FilterMac
import pytest

from homeassistant.components.bitvis.const import DEFAULT_PORT
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_DEVICE_MAC

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("patch_shared_listener")


async def test_setup_registers_mac_filter_on_listener(
    init_integration: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test integration setup registers a MAC filter on the shared listener."""
    assert init_integration.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    patch_shared_listener.register.assert_called_once()
    registered_filter = patch_shared_listener.register.call_args[0][0]
    assert isinstance(registered_filter, FilterMac)
    assert registered_filter.mac_address == TEST_DEVICE_MAC


async def test_two_entries_share_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_second_config_entry: MockConfigEntry,
    patch_shared_listener: MagicMock,
) -> None:
    """Test that two entries on the same port share one library listener."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_second_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_second_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_second_config_entry.state is ConfigEntryState.LOADED
    patch_shared_listener.start.assert_awaited_once_with(DEFAULT_PORT)
    assert patch_shared_listener.register.call_count == 2

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    patch_shared_listener.stop.assert_not_called()

    assert await hass.config_entries.async_unload(mock_second_config_entry.entry_id)
    patch_shared_listener.stop.assert_awaited_once()


async def test_setup_oserror_results_in_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that OSError from SharedListener.start results in SETUP_RETRY."""
    mock_shared_listener.start = AsyncMock(side_effect=OSError("port in use"))
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_runtime_error_results_in_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_shared_listener: MagicMock,
) -> None:
    """Test that RuntimeError from SharedListener.register results in SETUP_ERROR."""
    mock_shared_listener.register.side_effect = RuntimeError("duplicate filter")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
