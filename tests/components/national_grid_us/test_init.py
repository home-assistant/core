"""Tests for the National Grid US integration init."""

from unittest.mock import AsyncMock

from py_nationalgrid.exceptions import CannotConnectError, InvalidAuthError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import ENTITY_ELECTRIC_COST, ENTITY_ELECTRIC_USAGE, mock_billing_account


@pytest.mark.usefixtures("mock_national_grid_api")
async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test setup with auth error."""
    mock_national_grid_api.get_billing_account.side_effect = InvalidAuthError(
        "Bad creds"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(CannotConnectError("Timeout"), id="cannot_connect"),
        pytest.param(
            ValueError("GraphQL errors encountered"), id="graphql_value_error"
        ),
    ],
)
async def test_setup_entry_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
    error: Exception,
) -> None:
    """Test setup retries when the first refresh fails.

    py-nationalgrid raises a bare ValueError from GraphQLResponse.raise_on_errors
    for GraphQL error payloads, so it must be handled as an update failure.
    """
    mock_national_grid_api.get_billing_account.side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_sensor_missing_usage_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test sensors handle missing usage and cost data gracefully."""
    mock_national_grid_api.get_ami_energy_usages.side_effect = None
    mock_national_grid_api.get_ami_energy_usages.return_value = []
    mock_national_grid_api.get_energy_usage_costs.return_value = []

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(ENTITY_ELECTRIC_USAGE)
    assert state is not None
    assert state.state == "unknown"

    state = hass.states.get(ENTITY_ELECTRIC_COST)
    assert state is not None
    assert state.state == "unknown"


async def test_non_ami_meter_skips_usage_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test a non-AMI meter reports no usage without calling the usage API."""
    billing_account = mock_billing_account()
    for meter in billing_account["meter"]["nodes"]:
        meter["hasAmiSmartMeter"] = False
    mock_national_grid_api.get_billing_account.return_value = billing_account

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    state = hass.states.get(ENTITY_ELECTRIC_USAGE)
    assert state is not None
    assert state.state == "unknown"
    mock_national_grid_api.get_ami_energy_usages.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(CannotConnectError("Timeout"), id="cannot_connect"),
        pytest.param(
            ValueError("GraphQL errors encountered"), id="graphql_value_error"
        ),
    ],
)
@pytest.mark.parametrize(
    ("method", "entity_id"),
    [
        ("get_ami_energy_usages", ENTITY_ELECTRIC_USAGE),
        ("get_energy_usage_costs", ENTITY_ELECTRIC_COST),
    ],
)
async def test_sensor_api_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
    method: str,
    entity_id: str,
    error: Exception,
) -> None:
    """Test sensors handle usage and cost API errors gracefully.

    A bare ValueError from py-nationalgrid's raise_on_errors must degrade to an
    empty list like the typed errors, leaving the entry loaded.
    """
    getattr(mock_national_grid_api, method).side_effect = error

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_sensor_without_region_skips_cost_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_national_grid_api: AsyncMock,
) -> None:
    """Test cost retrieval is skipped when the billing account has no region."""
    mock_national_grid_api.get_billing_account.return_value["region"] = ""

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_national_grid_api.get_energy_usage_costs.assert_not_awaited()
