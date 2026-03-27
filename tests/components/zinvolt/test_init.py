"""Test the Zinvolt initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.zinvolt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Zinvolt device."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device({(DOMAIN, "ZVG011025120088")})
    assert device
    assert device == snapshot
