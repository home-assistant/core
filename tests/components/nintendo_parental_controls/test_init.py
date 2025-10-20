"""Test __init__ error handling."""

from unittest.mock import AsyncMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_invalid_authentication(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_failed_nintendo_authenticator: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test handling of invalid authentication."""
    await setup_integration(hass, mock_config_entry)

    # Ensure no entities are created
    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 0
    # Ensure the config entry is marked as error
    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR
