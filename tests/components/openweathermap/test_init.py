"""Test the OpenWeatherMap integration setup."""

from unittest.mock import AsyncMock

from pyopenweathermap import UnauthorizedError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.openweathermap.const import (
    DOMAIN,
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_V30,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir


@pytest.mark.parametrize("mode", ["v2.5"], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_deprecated_v25_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the V2.5 deprecation issue is linked to its config entry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"deprecated_v25_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.parametrize(
    "mode",
    [
        pytest.param(OWM_MODE_V30, id="weather"),
        pytest.param(OWM_MODE_AIRPOLLUTION, id="air_pollution"),
    ],
    indirect=True,
)
async def test_auth_failed_starts_reauth(
    hass: HomeAssistant,
    owm_client_mock: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an unauthorized API key starts the reauthentication flow."""
    owm_client_mock.get_weather.side_effect = UnauthorizedError("Invalid API key")
    owm_client_mock.get_air_pollution.side_effect = UnauthorizedError("Invalid API key")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
