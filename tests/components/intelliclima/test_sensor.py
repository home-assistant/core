"""Test IntelliClima Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
async def setup_intelliclima_sensor_only(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_cloud_interface: AsyncMock,
) -> AsyncGenerator[None]:
    """Set up IntelliClima integration with only the sensor platform."""
    with (
        patch("homeassistant.components.intelliclima.PLATFORMS", [Platform.SENSOR]),
    ):
        await setup_integration(hass, mock_config_entry)
        # Let tests run against this initialized state
        yield


async def test_all_sensor_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_cloud_interface: AsyncMock,
) -> None:
    """Test all entities."""

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # There should be exactly three sensor entities
    sensor_entries = [
        entry
        for entry in entity_registry.entities.values()
        if entry.platform == "intelliclima" and entry.domain == SENSOR_DOMAIN
    ]
    assert len(sensor_entries) == 3

    entity_entry = sensor_entries[0]
    # Device should exist and match snapshot
    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot
