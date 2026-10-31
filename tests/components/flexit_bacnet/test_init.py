"""Tests for the Flexit Nordic (BACnet) __init__."""

from datetime import timedelta
from unittest.mock import AsyncMock

from flexit_bacnet import DecodingError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.flexit_bacnet.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.util.dt import utcnow

from . import setup_with_selected_platforms


async def test_loading_and_unloading_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flexit_bacnet: AsyncMock,
) -> None:
    """Test loading and unloading a config entry."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ConnectionError, id="connection_error"),
        pytest.param(DecodingError, id="decoding_error"),
    ],
)
async def test_failed_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flexit_bacnet: AsyncMock,
    error: type[Exception],
) -> None:
    """Test failed initialization."""
    mock_flexit_bacnet.update.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TimeoutError, id="timeout"),
        pytest.param(ConnectionError, id="connection_error"),
        pytest.param(DecodingError, id="decoding_error"),
    ],
)
async def test_update_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flexit_bacnet: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    error: type[Exception],
) -> None:
    """Test polling failures make entities unavailable until a successful update."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.CLIMATE])
    coordinator = mock_config_entry.runtime_data
    initial_state = hass.states.get("climate.device_name").state
    assert initial_state != STATE_UNAVAILABLE

    mock_flexit_bacnet.update.side_effect = error
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, utcnow())
    await hass.async_block_till_done()

    assert isinstance(coordinator.last_exception, UpdateFailed)
    assert isinstance(coordinator.last_exception.__cause__, error)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.device_name").state == STATE_UNAVAILABLE
    assert "Unexpected error fetching" not in caplog.text

    mock_flexit_bacnet.update.side_effect = None
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass, utcnow())
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("climate.device_name").state == initial_state
