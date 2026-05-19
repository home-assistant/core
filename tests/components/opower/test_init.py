"""Tests for the Opower integration."""

from unittest.mock import AsyncMock

from opower.exceptions import ApiException, CannotConnect, InvalidAuth
import pytest

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


async def test_setup_unload_entry(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_opower_api.async_login.assert_awaited_once()
    mock_opower_api.async_get_forecast.assert_awaited_once()
    mock_opower_api.async_get_accounts.assert_awaited_once()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


@pytest.mark.parametrize(
    ("login_side_effect", "expected_state"),
    [
        (
            CannotConnect(),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            InvalidAuth(),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_login_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    login_side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test for login error."""
    mock_opower_api.async_login.side_effect = login_side_effect

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected_state


async def test_get_forecast_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting forecast."""
    mock_opower_api.async_get_forecast.side_effect = ApiException(
        message="forecast error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_accounts_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting accounts."""
    mock_opower_api.async_get_accounts.side_effect = ApiException(
        message="accounts error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_get_cost_reads_error(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
) -> None:
    """Test for API error when getting cost reads."""
    mock_opower_api.async_get_cost_reads.side_effect = ApiException(
        message="cost reads error", url=""
    )

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_national_grid_migration_repair_issue(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_opower_api: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that a repair issue is created for National Grid utilities."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "utility": "National Grid (MA)",
            "username": "test-user",
            "password": "test-password",
        },
        title="National Grid (MA) (test-user)",
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    issue = issue_registry.async_get_issue(
        DOMAIN, f"national_grid_migration_{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "national_grid_migration"
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_placeholders["utility"] == "National Grid (MA)"
    assert "national_grid_us" in issue.translation_placeholders["add_integration"]


async def test_non_national_grid_no_migration_repair(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opower_api: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test that no repair issue is created for non-National Grid utilities."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    issues = [
        issue
        for issue in issue_registry.issues.values()
        if issue.translation_key == "national_grid_migration"
    ]
    assert len(issues) == 0
