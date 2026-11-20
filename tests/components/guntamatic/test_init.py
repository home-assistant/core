"""Test the Guntamatic integration setup."""

from unittest.mock import MagicMock

from guntamatic.heater import NoSerialException
import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
) -> None:
    """Test successful setup of the integration."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "translation_key", "placeholders"),
    [
        (
            requests.exceptions.ConnectionError("Cannot connect"),
            "communication_error",
            {"error": "Cannot connect"},
        ),
        (
            requests.exceptions.ReadTimeout("Timed out"),
            "communication_error",
            {"error": "Timed out"},
        ),
        (NoSerialException, "no_serial", None),
    ],
)
async def test_setup_entry_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_heater: MagicMock,
    side_effect: Exception,
    translation_key: str,
    placeholders: dict[str, str] | None,
) -> None:
    """Test setup fails correctly for different error types."""
    mock_heater.parse_data.side_effect = side_effect
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert mock_config_entry.error_reason_translation_placeholders == placeholders
