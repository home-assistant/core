"""Advanced tests for the LoJack device tracker platform."""

from unittest.mock import AsyncMock

from homeassistant.components.device_tracker import SourceType
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device_tracker_source_type(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test device tracker source type is GPS."""
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("device_tracker.2021_honda_accord")
    assert state is not None
    assert state.attributes["source_type"] == SourceType.GPS
