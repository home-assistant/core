"""Test the Monarch Money coordinator."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
from gql.transport.exceptions import TransportError, TransportServerError
from monarchmoney import LoginFailedException
import pytest

from homeassistant.components.monarch_money.coordinator import (
    MonarchMoneyDataUpdateCoordinator,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_cashflow_year_follows_configured_time_zone(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test the cashflow window uses the year of the configured time zone.

    The clock is stopped at a moment that is still 2025 in UTC but already 2026
    in Pacific/Kiritimati, so a query built from the host clock would ask for
    the wrong year.
    """
    await hass.config.async_set_time_zone("Pacific/Kiritimati")  # UTC+14
    freezer.move_to("2025-12-31T12:00:00+00:00")

    await setup_integration(hass, mock_config_entry)

    mock_config_api.return_value.get_cashflow_summary.assert_called_with(
        start_date="2026-01-01", end_date="2026-12-31"
    )


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(LoginFailedException("expired"), id="login_failed"),
        pytest.param(
            TransportServerError("unauthorized", code=401), id="http_unauthorized"
        ),
    ],
)
async def test_setup_auth_error_starts_reauthentication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    api_error: Exception,
) -> None:
    """Test setup authentication errors start reauthentication."""
    mock_config_api.return_value.get_subscription_details.side_effect = api_error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_update_auth_error_starts_reauthentication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
) -> None:
    """Test refresh authentication errors start reauthentication."""
    await setup_integration(hass, mock_config_entry)
    coordinator: MonarchMoneyDataUpdateCoordinator = mock_config_entry.runtime_data
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.side_effect = (
        TransportServerError("forbidden", code=403)
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not coordinator.last_update_success
    state = hass.states.get("sensor.cashflow_expense_year_to_date")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["step_id"] == "reauth_confirm"


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(TransportServerError("server error", code=500), id="http_error"),
        pytest.param(TimeoutError(), id="timeout"),
    ],
)
async def test_setup_connection_error_is_retryable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    api_error: Exception,
) -> None:
    """Test setup connection errors schedule a retry."""
    mock_config_api.return_value.get_subscription_details.side_effect = api_error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress() == []


@pytest.mark.parametrize(
    "api_error",
    [
        pytest.param(TransportError("transport error"), id="transport_error"),
        pytest.param(ClientError("client error"), id="client_error"),
    ],
)
async def test_update_connection_error_is_retryable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_api: AsyncMock,
    api_error: Exception,
) -> None:
    """Test refresh connection errors mark data unavailable without reauth."""
    await setup_integration(hass, mock_config_entry)
    coordinator: MonarchMoneyDataUpdateCoordinator = mock_config_entry.runtime_data
    mock_config_api.return_value.get_accounts_as_dict_with_id_key.side_effect = (
        api_error
    )

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not coordinator.last_update_success
    state = hass.states.get("sensor.cashflow_expense_year_to_date")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
    assert hass.config_entries.flow.async_progress() == []
