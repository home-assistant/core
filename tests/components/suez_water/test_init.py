"""Test init of Suez water component."""

from unittest.mock import patch

from pysuez.client import PySuezError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import create_config_entry


async def test_init_success(hass: HomeAssistant) -> None:
    """Test setup and that we can create the entry."""
    with (
        patch("pysuez.client.SuezClient.check_credentials", return_value=True),
        patch(
            "homeassistant.components.suez_water.coordinator.SuezWaterCoordinator.async_config_entry_first_refresh",
            return_value=True,
        ),
    ):
        entry = await create_config_entry(hass)
        assert entry.state is ConfigEntryState.LOADED


async def test_invalid_credentials(hass: HomeAssistant) -> None:
    """Test result with invalid credentials."""
    with patch("pysuez.client.SuezClient.check_credentials", return_value=False):
        entry = await create_config_entry(hass)
        assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test result with connection error."""
    with patch(
        "pysuez.client.SuezClient.check_credentials", side_effect=PySuezError("Test")
    ):
        entry = await create_config_entry(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
