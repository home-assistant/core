"""Tests for the Tank Utility integration setup and teardown."""

from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.tank_utility.const import DOMAIN
from homeassistant.components.tank_utility.coordinator import (
    TankUtilityDataUpdateCoordinator,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def _mock_http_error(status_code: int) -> requests.exceptions.HTTPError:
    """Create a mock HTTPError with a response."""
    response = requests.Response()
    response.status_code = status_code
    return requests.exceptions.HTTPError(response=response)


@pytest.mark.usefixtures("mock_get_data")
async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup and unload of a config entry."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, TankUtilityDataUpdateCoordinator)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
) -> None:
    """Test setup entry when authentication fails triggers reauth."""
    mock_get_data.side_effect = _mock_http_error(requests.codes.unauthorized)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"
    assert flows[0]["handler"] == DOMAIN


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.ConnectTimeout,
        _mock_http_error(requests.codes.internal_server_error),
    ],
)
async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_data: MagicMock,
    exception: Exception,
) -> None:
    """Test setup entry when network connection fails initiates setup retry."""
    mock_get_data.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
