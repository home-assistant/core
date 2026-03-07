"""Test the Fressnapf Tracker integration init."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fressnapftracker import (
    FressnapfTrackerError,
    FressnapfTrackerInvalidTrackerResponseError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.fressnapf_tracker.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .conftest import MOCK_SERIAL_NUMBER

from tests.common import MockConfigEntry


@pytest.fixture
def mock_api_client_malformed_tracker() -> Generator[MagicMock]:
    """Mock the ApiClient for a malformed tracker response in _tracker_is_valid."""
    with patch(
        "homeassistant.components.fressnapf_tracker.ApiClient",
        autospec=True,
    ) as mock_api_client:
        client = mock_api_client.return_value
        client.get_tracker = AsyncMock(
            side_effect=FressnapfTrackerInvalidTrackerResponseError("Invalid tracker")
        )
        yield client


@pytest.mark.usefixtures("mock_auth_client", "mock_api_client_init")
async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_auth_client", "mock_api_client_init")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unload of config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_auth_client")
async def test_setup_entry_tracker_is_valid_api_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client_init: MagicMock,
) -> None:
    """Test setup retries when API returns error during _tracker_is_valid."""
    mock_config_entry.add_to_hass(hass)

    mock_api_client_init.get_tracker = AsyncMock(
        side_effect=FressnapfTrackerError("API Error")
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("init_integration")
async def test_state_entity_device_snapshots(
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensor entity is created correctly."""
    device_entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert device_entries
    for device_entry in device_entries:
        assert device_entry == snapshot(name=f"{device_entry.name}-entry"), (
            f"device entry snapshot failed for {device_entry.name}"
        )


@pytest.mark.usefixtures("mock_auth_client", "mock_api_client_malformed_tracker")
async def test_invalid_tracker(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an issue is created when an invalid tracker is detected."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(issue_registry.issues) == 1

    issue_id = f"invalid_fressnapf_tracker_{MOCK_SERIAL_NUMBER}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("mock_auth_client", "mock_api_client_malformed_tracker")
async def test_invalid_tracker_already_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that an existing issue is not duplicated."""
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"invalid_fressnapf_tracker_{MOCK_SERIAL_NUMBER}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="invalid_fressnapf_tracker",
        translation_placeholders={"tracker_id": MOCK_SERIAL_NUMBER},
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(issue_registry.issues) == 1
