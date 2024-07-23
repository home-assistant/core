"""Tests for the AirGradient integration."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.airgradient import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry
from tests.components.airgradient import setup_integration


async def test_device_info(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_airgradient_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry integration."""
    await setup_integration(hass, mock_config_entry)
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot
