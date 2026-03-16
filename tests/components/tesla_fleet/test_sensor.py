"""Test the Tesla Fleet sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import VEHICLE_DATA_ALT

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
) -> None:
    """Tests that the sensor entities are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)

    # Coordinator refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, normal_config_entry.entry_id, entity_registry, snapshot)


@pytest.mark.parametrize(
    ("entity_id", "initial", "restored"),
    [
        ("sensor.test_battery_level", "77", "77"),
        ("sensor.test_outside_temperature", "30", "30"),
        ("sensor.test_time_to_arrival", "2024-01-01T00:00:06+00:00", STATE_UNAVAILABLE),
    ],
)
async def test_sensors_restore(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    normal_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    entity_id: str,
    initial: str,
    restored: str,
) -> None:
    """Test if the sensor should restore it's state or not when vehicle is offline."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    assert hass.states.get(entity_id).state == initial

    mock_vehicle_data.side_effect = VehicleOffline

    with patch("homeassistant.components.tesla_fleet.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    assert hass.states.get(entity_id).state == restored
