"""Tests for the Palazzetti integration."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pypalazzetti.exceptions import CommunicationError, ValidationError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.palazzetti.const import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
) -> None:
    """Test the Palazzetti configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
    snapshot: SnapshotAssertion,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test the device information."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, "11:22:33:44:55:66"), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(CommunicationError, id="communication_error"),
        pytest.param(ValidationError, id="validation_error"),
    ],
)
async def test_setup_entry_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
    exception: type[Exception],
) -> None:
    """Test setup entry failure when coordinator _async_setup fails."""
    mock_palazzetti_client.connect.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(CommunicationError, id="communication_error"),
        pytest.param(ValidationError, id="validation_error"),
    ],
)
async def test_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_palazzetti_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
    exception: type[Exception],
) -> None:
    """Test coordinator update failure."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_palazzetti_client.update_state.side_effect = exception
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data
    assert not coordinator.last_update_success
