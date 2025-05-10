"""Test the Tessie init."""

from unittest.mock import patch

from tesla_fleet_api.exceptions import TeslaFleetError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import error_auth, error_connection, error_unknown, setup_platform


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles
) -> None:
    """Test init with an authentication error."""

    mock_get_state_of_all_vehicles.side_effect = error_auth()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles
) -> None:
    """Test init with an client response error."""

    mock_get_state_of_all_vehicles.side_effect = error_unknown()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_connection_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles
) -> None:
    """Test init with a network connection error."""

    mock_get_state_of_all_vehicles.side_effect = error_connection()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_products_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on products."""

    with patch(
        "homeassistant.components.tessie.Tessie.products", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_scopes_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on scopes."""

    with patch(
        "homeassistant.components.tessie.Tessie.scopes", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY
