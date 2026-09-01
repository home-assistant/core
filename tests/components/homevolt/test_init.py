"""Test the Homevolt init module."""

from unittest.mock import MagicMock

from homevolt import HomevoltAuthenticationError, HomevoltConnectionError
import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.components.homevolt.coordinator import HomevoltDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_homevolt_client.close_connection.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_state"),
    [
        (
            HomevoltConnectionError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
        ),
        (
            HomevoltAuthenticationError("Authentication failed"),
            ConfigEntryState.SETUP_ERROR,
        ),
    ],
)
async def test_config_entry_setup_failure(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    side_effect: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test the Homevolt configuration entry setup failures."""
    mock_homevolt_client.update_info.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert mock_config_entry.state is expected_state


async def test_coordinator_update_error_is_translated(
    hass: HomeAssistant,
    mock_homevolt_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator communication errors are translatable."""
    mock_homevolt_client.update_info.side_effect = HomevoltConnectionError(
        "Connection failed"
    )
    coordinator = HomevoltDataUpdateCoordinator(
        hass, mock_config_entry, mock_homevolt_client
    )

    with pytest.raises(UpdateFailed) as exc_info:
        await coordinator._async_update_data()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"
    assert exc_info.value.translation_placeholders == {"error": "Connection failed"}
