"""Test the Antifurto365 iAlarm init."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ialarm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import TEST_MAC


async def test_setup_entry(
    hass: HomeAssistant, ialarm_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    ialarm_api.return_value.get_mac.assert_awaited_once()
    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize("side_effect", [ConnectionError, TimeoutError])
async def test_setup_not_ready(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: type[Exception],
) -> None:
    """Test setup failed because we can't connect to the alarm system."""
    ialarm_api.return_value.get_mac.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    ialarm_api.return_value.shutdown.assert_awaited_once()


@pytest.mark.parametrize(
    ("method", "side_effect", "expected_state"),
    [
        pytest.param(
            "get_mac", ValueError, ConfigEntryState.SETUP_ERROR, id="unexpected_error"
        ),
        pytest.param(
            "get_status",
            ConnectionError,
            ConfigEntryState.SETUP_RETRY,
            id="first_refresh_failed",
        ),
    ],
)
async def test_setup_failure_closes_connection(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
    side_effect: type[Exception],
    expected_state: ConfigEntryState,
) -> None:
    """Test the connection is closed whatever makes the setup fail."""
    getattr(ialarm_api.return_value, method).side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state
    ialarm_api.return_value.shutdown.assert_awaited_once()


async def test_device_registry(
    hass: HomeAssistant,
    ialarm_api: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the device registry entry, including the network MAC connection."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, TEST_MAC), mock_config_entry.entry_id
    )
    assert device_entry == snapshot


async def test_unload_entry(
    hass: HomeAssistant, ialarm_api: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test being able to unload an entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    ialarm_api.return_value.shutdown.assert_awaited_once()
