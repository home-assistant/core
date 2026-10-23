"""Tests for the saj integration initialization."""

from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pysaj
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.saj.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


@pytest.mark.parametrize("connection_method", ["ethernet", "wifi"], indirect=True)
@pytest.mark.usefixtures("mock_pysaj_saj")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_setup_entry for ethernet and wifi connections."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test async_setup_entry handles connection failures."""
    mock_pysaj_saj.read.return_value = False
    entry = await setup_integration(hass, mock_config_entry)
    # Entry should be in SETUP_RETRY state when setup fails
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("connection_method", ["wifi"], indirect=True)
async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
) -> None:
    """Test async_setup_entry fails WiFi auth at setup without endless retries."""
    mock_pysaj_saj.read.side_effect = pysaj.UnauthorizedException("Auth failed")
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.parametrize("connection_method", ["wifi"], indirect=True)
async def test_update_auth_failed_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an auth error during a scheduled refresh starts a reauth flow."""
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED

    mock_pysaj_saj.read.side_effect = pysaj.UnauthorizedException("Auth failed")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(
            pysaj.UnauthorizedException("unexpected"), id="ethernet_unauthorized"
        ),
        pytest.param(
            pysaj.UnexpectedResponseException("bad response"), id="unexpected_response"
        ),
        pytest.param(TimeoutError("timed out"), id="timeout"),
        pytest.param(OSError("network unreachable"), id="os_error"),
        pytest.param(Exception("Unexpected error"), id="unexpected"),
        pytest.param(RuntimeError("Unexpected runtime error"), id="runtime_error"),
    ],
)
async def test_setup_entry_retries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pysaj_saj: MagicMock,
    exception: Exception,
) -> None:
    """Test errors during setup result in a retry."""
    mock_pysaj_saj.read.side_effect = exception
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_pysaj_saj")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_unload_entry."""
    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
