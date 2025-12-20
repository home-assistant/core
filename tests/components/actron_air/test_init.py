"""Test the Actron Air integration initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from actron_neo_api import ActronAirAPIError, ActronAirAuthError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_setup import FrozenDateTimeFactory


async def test_setup_entry(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_coordinator_update_auth_error(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test coordinator handles authentication error during update."""
    # Setup integration first
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Now make the update fail with auth error
    mock_actron_api.update_status.side_effect = ActronAirAuthError("Auth failed")

    # Freeze time and trigger an update
    freezer.tick(timedelta(seconds=31))
    await hass.async_block_till_done()
    await hass.async_block_till_done()  # Extra wait to ensure issue registry is updated
    # After auth error during update, ConfigEntryAuthFailed is raised which triggers reauth
    assert mock_actron_api.update_status.called

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Check that a reauth issue was created
    issue_registry = ir.async_get(hass)
    issue_id = (
        f"config_entry_reauth_{mock_config_entry.domain}_{mock_config_entry.entry_id}"
    )
    issue = issue_registry.async_get_issue("homeassistant", issue_id)
    assert issue is not None
    assert issue.issue_domain == mock_config_entry.domain


async def test_setup_entry_auth_error_on_get_systems(
    hass: HomeAssistant, mock_actron_api: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup fails with ConfigEntryAuthFailed when authentication fails on get_ac_systems."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.get_ac_systems = AsyncMock(
        side_effect=ActronAirAuthError("Auth failed")
    )

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ActronAirAuthError("Auth failed"), ConfigEntryState.SETUP_ERROR),
        (ActronAirAPIError("API error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_error_on_update_status(
    hass: HomeAssistant,
    mock_actron_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup fails appropriately when error occurs on update_status."""
    mock_config_entry.add_to_hass(hass)
    mock_actron_api.update_status = AsyncMock(side_effect=exception)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert result is False
    assert mock_config_entry.state is expected_state
