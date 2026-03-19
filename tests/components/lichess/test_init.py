"""Test the Lichess initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lichess.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lichess_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lichess device."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device({(DOMAIN, "drnykterstien")})
    assert device
    assert device == snapshot
