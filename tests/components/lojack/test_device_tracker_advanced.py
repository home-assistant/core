"""Advanced tests for the LoJack device tracker platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.device_tracker import SourceType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


def _make_client(mock_device: MagicMock) -> AsyncMock:
    """Build a mock client for device_tracker tests."""
    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


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
