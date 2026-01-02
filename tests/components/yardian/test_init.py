"""Test the initialization of Yardian."""

from unittest.mock import AsyncMock

from pyyardian import NotAuthorizedException

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry


async def test_setup_unauthorized(
    hass: HomeAssistant,
    mock_yardian_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test setup when unauthorized."""
    mock_yardian_client.fetch_device_state.side_effect = NotAuthorizedException

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
