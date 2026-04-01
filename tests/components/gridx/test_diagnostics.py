"""Tests for the GridX diagnostics."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.components.gridx.diagnostics import async_get_config_entry_diagnostics
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import MOCK_HIST_DATA, MOCK_LIVE_DATA, OEM, PASSWORD, USERNAME


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> MockConfigEntry:
    """Load the GridX integration with a mocked connector."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
    )
    entry.add_to_hass(hass)

    mock_gridx_connector.retrieve_live_data.return_value = [MOCK_LIVE_DATA]
    mock_gridx_connector.retrieve_historical_data.return_value = MOCK_HIST_DATA

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_diagnostics_redacts_password(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test diagnostics payload includes data and redacts secrets."""
    result = await async_get_config_entry_diagnostics(hass, setup_integration)

    assert result["config_entry"][CONF_USERNAME] == USERNAME
    assert result["config_entry"][CONF_PASSWORD] == "**REDACTED**"
    assert result["live_data"] == MOCK_LIVE_DATA
    assert result["historical_data"]["total"] == MOCK_HIST_DATA[0]["total"]
