"""Tests for the Zendure sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import build_snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the sensor entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_unknown_values(
    hass: HomeAssistant,
    mock_read: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an invalid value and an unrecognized state code show as unknown."""
    snapshot = build_snapshot()
    mock_read.return_value = replace(
        snapshot,
        properties={**snapshot.properties, "remainOutTime": None, "packState": 9},
    )
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        hass.states.get("sensor.solarflow_2400_ac_remaining_discharge_time").state
        == STATE_UNKNOWN
    )
    assert hass.states.get("sensor.solarflow_2400_ac_battery_state").state == (
        STATE_UNKNOWN
    )


@pytest.mark.usefixtures("mock_zendure")
async def test_missing_key_creates_no_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_read: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a property the device does not report creates no entity."""
    snapshot = build_snapshot()
    properties = dict(snapshot.properties)
    del properties["solarPower4"]
    mock_read.return_value = replace(snapshot, properties=properties)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not entity_registry.async_get_entity_id(
        "sensor", "zendure", "TESTDEV00000001_solarPower4"
    )
    assert entity_registry.async_get_entity_id(
        "sensor", "zendure", "TESTDEV00000001_solarPower3"
    )
