"""Tests for the Smarty component."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.smarty.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_smarty: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device."""
    await setup_integration(hass, mock_config_entry)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device
    assert device == snapshot
