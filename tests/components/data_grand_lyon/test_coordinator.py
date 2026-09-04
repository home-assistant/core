"""Tests for the Data Grand Lyon alerts coordinator."""

from unittest.mock import AsyncMock, Mock

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_alerts_filtered_by_line(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test alerts are filtered to the monitored line only."""
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    data = mock_line_config_entry.runtime_data.alerts_coordinator.data
    assert list(data) == ["line_1"]
    assert [alert.titre for alert in data["line_1"]] == [
        "Déviée dir. Cordeliers",
        "Fête de la Musique",
    ]


async def test_line_with_no_alert_keeps_its_key(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a line without any alert is still present in the coordinator data."""
    mock_tcl_client.get_tcl_alerts.return_value = []
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    data = mock_line_config_entry.runtime_data.alerts_coordinator.data
    assert data == {"line_1": []}


async def test_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_line_config_entry: MockConfigEntry,
    mock_tcl_client: AsyncMock,
) -> None:
    """Test a 401 on the alerts fetch starts the reauth flow."""
    mock_tcl_client.get_tcl_alerts.side_effect = ClientResponseError(
        Mock(), Mock(), status=401
    )
    mock_line_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_line_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_line_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(ClientResponseError(Mock(), Mock(), status=500), id="http_error"),
        pytest.param(ClientConnectionError("boom"), id="connection_error"),
        pytest.param(TimeoutError, id="timeout"),
    ],
)
async def test_fetch_failure_retries_setup(
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
