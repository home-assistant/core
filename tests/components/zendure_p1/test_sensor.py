"""Tests for the Zendure Smart Meter P1 sensor platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from zendure_p1 import Report

from homeassistant.components.zendure_p1.const import UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor entities match the snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_values(
    hass: HomeAssistant,
    mock_zendure_p1_client: AsyncMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor entities expose values from the coordinator."""
    for key, expected in (
        ("a_apparent_power", "100"),
        ("b_apparent_power", "200"),
        ("c_apparent_power", "300"),
        ("total_power", "600"),
    ):
        unique_id = f"SN123456-{key}"
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "zendure_p1", unique_id
        )
        assert entity_id is not None, f"Entity {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected

    mock_zendure_p1_client.get_report.return_value = Report(
        timestamp=2000000,
        device_id="SN123456",
        a_apparent_power=150,
        b_apparent_power=250,
        c_apparent_power=350,
        total_power=750,
    )
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for key, expected in (
        ("a_apparent_power", "150"),
        ("b_apparent_power", "250"),
        ("c_apparent_power", "350"),
        ("total_power", "750"),
    ):
        unique_id = f"SN123456-{key}"
        entity_id = entity_registry.async_get_entity_id(
            "sensor", "zendure_p1", unique_id
        )
        assert entity_id is not None, f"Entity {unique_id} not found"
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected
