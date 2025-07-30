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


async def test_setup_entry_missing_login_service_url(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    mock_opower_api: AsyncMock,
) -> None:
    """Test issue is created when login service URL is missing for a utility that requires it."""

    config_entry = MockConfigEntry(
        title="Pacific Gas & Electric (test-username)",
        domain=DOMAIN,
        data={
            "utility": "Pacific Gas and Electric Company (PG&E)",
            "username": "test-username",
            "password": "test-password",
        },
        options={},
    )
    config_entry.add_to_hass(hass)

    # Setup should fail and create an issue
    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    issue_id = f"login_service_url_missing_{config_entry.entry_id}"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.ERROR

    # Now, add the URL via options and re-run setup
    hass.config_entries.async_update_entry(
        config_entry, options={"login_service_url": "http://localhost:1234"}
    )
    await hass.config_entries.async_reload(config_entry.entry_id)

    # Setup should succeed and the issue should be deleted
    assert config_entry.state is ConfigEntryState.LOADED
    issue = ir.async_get(hass).async_get_issue(DOMAIN, issue_id)
    assert issue is None
