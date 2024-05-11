"""Test the Teslemetry binary sensor platform."""

import pytest
from syrupy import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Tests that the binary sensor entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_binary_sensor_offline(
    hass: HomeAssistant,
    mock_vehicle_data,
) -> None:
    """Tests that the binary sensor entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, [Platform.BINARY_SENSOR])
    state = hass.states.get("binary_sensor.test_status")
    assert state.state == STATE_UNKNOWN
