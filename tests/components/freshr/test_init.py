"""Test the Fresh-r initialization."""

from aiohttp import ClientError
from pyfreshr.exceptions import ApiResponseError, LoginError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MagicMock, MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading the config entry."""
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_login_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
) -> None:
    """Test that a login error during setup triggers reauthentication."""
    mock_freshr_client.login.side_effect = LoginError("bad credentials")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [ApiResponseError("parse error"), ClientError("network error")],
)
async def test_setup_fetch_devices_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    exception: Exception,
) -> None:
    """Test that a fetch_devices error during setup triggers a retry."""
    mock_freshr_client.fetch_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_no_devices(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that an empty device list sets up successfully with no entities."""
    mock_freshr_client.fetch_devices.return_value = []
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (
        er.async_entries_for_config_entry(entity_registry, mock_config_entry.entry_id)
        == []
    )
