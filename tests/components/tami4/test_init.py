"""Test the Tami4 component."""
import pytest
from Tami4EdgeAPI import exceptions

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import create_config_entry


async def test_init_success(mock_api, hass: HomeAssistant) -> None:
    """Test setup and that we can create the entry."""

    entry = await create_config_entry(hass)
    assert entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "mock_get_water_quality", [exceptions.APIRequestFailedException], indirect=True
)
async def test_init_with_api_error(mock_api, hass: HomeAssistant) -> None:
    """Test init with api error."""

    entry = await create_config_entry(hass)
    assert entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("mock__get_devices", "expected_state"),
    [
        (
            exceptions.RefreshTokenExpiredException,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            exceptions.TokenRefreshFailedException,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    indirect=["mock__get_devices"],
)
async def test_init_error_raised(
    mock_api, hass: HomeAssistant, expected_state: ConfigEntryState
) -> None:
    """Test init when an error is raised."""

    entry = await create_config_entry(hass)
    assert entry.state == expected_state


async def test_load_unload(mock_api, hass: HomeAssistant) -> None:
    """Config entry can be unloaded."""

    entry = await create_config_entry(hass)

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
