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


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (ApiResponseError("parse error"), ConfigEntryState.SETUP_RETRY),
        (ClientError("network error"), ConfigEntryState.SETUP_RETRY),
        (LoginError("bad credentials"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_freshr_client: MagicMock,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test that an error during setup sets the config entry to the expected state."""
    mock_freshr_client.fetch_devices.side_effect = exception
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is entry_state


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
