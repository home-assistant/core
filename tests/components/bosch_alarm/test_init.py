"""Tests for bosch alarm integration init."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def disable_platform_only():
    """Disable platforms to speed up tests."""
    with patch("homeassistant.components.bosch_alarm.PLATFORMS", []):
        yield


@pytest.mark.parametrize("model", ["solution_3000"])
@pytest.mark.parametrize("exception", [PermissionError()])
async def test_incorrect_auth(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test errors with incorrect auth."""
    mock_panel.connect.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize("model", ["solution_3000"])
@pytest.mark.parametrize("exception", [TimeoutError()])
async def test_connection_error(
    hass: HomeAssistant,
    mock_panel: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test errors with incorrect auth."""
    mock_panel.connect.side_effect = exception
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
