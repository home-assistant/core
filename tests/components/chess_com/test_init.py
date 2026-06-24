"""Test the Chess.com initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.chess_com.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_chess_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Chess.com device."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device({(DOMAIN, "532748851")})
    assert device
    assert device == snapshot
