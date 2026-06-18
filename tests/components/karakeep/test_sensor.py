"""Tests for the Karakeep sensor platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .const import TEST_VERSION

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Karakeep sensors."""
    with patch("homeassistant.components.karakeep.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_device_info(
    hass: HomeAssistant,
    mock_karakeep_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry entry."""
    await setup_integration(hass, mock_config_entry)

    device_entry = device_registry.async_get_device(
        identifiers={("karakeep", mock_config_entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry.name == "Karakeep"
    assert device_entry.manufacturer == "Karakeep"
    assert device_entry.sw_version == TEST_VERSION
