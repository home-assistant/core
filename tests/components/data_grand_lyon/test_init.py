"""Tests for the Data Grand Lyon integration setup."""

from types import MappingProxyType
from unittest.mock import AsyncMock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant.components.data_grand_lyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState, ConfigSubentry
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_subentry_added_reloads(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test that adding a subentry reloads the entry and creates new entities."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.c3_stop_100_next_departure_1") is not None
    assert hass.states.get("sensor.t1_stop_200_next_departure_1") is None

    initial_call_count = mock_tcl_client.get_tcl_passages.call_count

    hass.config_entries.async_add_subentry(
        mock_config_entry,
        ConfigSubentry(
            data=MappingProxyType({CONF_LINE: "T1", CONF_STOP_ID: 200}),
            subentry_type=SUBENTRY_TYPE_STOP,
            title="T1 - Stop 200",
            unique_id="T1_200",
        ),
    )
    await hass.async_block_till_done()

    assert mock_tcl_client.get_tcl_passages.call_count > initial_call_count
    assert hass.states.get("sensor.t1_stop_200_next_departure_1") is not None


@pytest.mark.parametrize(
    ("entry_fixture", "client_method"),
    [
        pytest.param("mock_config_entry", "get_tcl_passages", id="passages"),
        pytest.param("mock_line_config_entry", "get_tcl_alerts", id="alerts"),
    ],
)
async def test_setup_triggers_reauth_on_auth_failure(
    hass: HomeAssistant,
    mock_tcl_client: AsyncMock,
    request: pytest.FixtureRequest,
    entry_fixture: str,
    client_method: str,
) -> None:
    """Test that an auth failure during setup triggers a reauth flow."""
    getattr(mock_tcl_client, client_method).side_effect = ClientResponseError(
        None, None, status=401
    )
    config_entry: MockConfigEntry = request.getfixturevalue(entry_fixture)

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"].get("source") == SOURCE_REAUTH for flow in flows)


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(ClientResponseError(None, None, status=500), id="http_error"),
        pytest.param(ClientConnectionError("boom"), id="connection_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_alerts_fetch_failure_retries_setup(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
    side_effect: Exception,
) -> None:
    """Test a failed alerts fetch leaves the entry retrying, not errored."""
    mock_tcl_client.get_tcl_alerts.side_effect = side_effect
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_line_config_entry.state is ConfigEntryState.SETUP_RETRY
