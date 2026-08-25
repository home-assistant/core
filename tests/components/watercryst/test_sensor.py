"""Tests for WATERCryst BIOCAT sensors."""

from unittest.mock import AsyncMock

from pyocat.models import StateResponse
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.watercryst.coordinator import (
    WatercrystStateUpdateCoordinator,
)
from homeassistant.components.watercryst.sensor import (
    WatercrystSensor,
    WatercrystSensorEntityDescription,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, patch, snapshot_platform


@pytest.mark.usefixtures("mock_api_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: EntityRegistry,
    config_entry: MockConfigEntry,
) -> None:
    """Test all sensor entities."""
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.watercryst._PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_missing_data(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api_client: AsyncMock,
) -> None:
    """Test the native value when there is no data."""
    coordinator = WatercrystStateUpdateCoordinator(
        hass=hass,
        config_entry=config_entry,
        client=mock_api_client,
    )

    description = WatercrystSensorEntityDescription[StateResponse](
        key="event.event_id",
        translation_key="event_id",
        icon="mdi:alert-circle-outline",
        value_fn=lambda data: data.event.event_id if data.event else None,
    )

    entity = WatercrystSensor(config_entry, coordinator, description)

    assert entity.native_value is None
