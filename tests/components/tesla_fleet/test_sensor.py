"""Test the Tesla Fleet sensor platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import VEHICLE_ASLEEP, VEHICLE_DATA_ALT

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
        ("sensor.test_2", "77", "77"),
        ("sensor.test_23", "30", "30"),
        ("sensor.test_30", "2024-01-01T00:00:06+00:00", STATE_UNAVAILABLE),
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


async def test_sensor_restored_value_not_overwritten_by_coordinator(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_vehicle_state: AsyncMock,
) -> None:
    """Test that restored sensor values survive coordinator updates when vehicle is asleep."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    entity_id = "sensor.test_2"
    assert hass.states.get(entity_id).state == "77"

    # Vehicle goes offline, reload to trigger restore
    mock_vehicle_data.side_effect = VehicleOffline

    with patch("homeassistant.components.tesla_fleet.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    # Value should be restored
    state = hass.states.get(entity_id)
    assert state.state == "77"

    # Simulate another coordinator update while vehicle is still asleep
    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    mock_vehicle_data.side_effect = VehicleOffline
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Restored value should still be shown, not overwritten
    state = hass.states.get(entity_id)
    assert state.state == "77"


async def test_sensor_restored_value_cleared_on_fresh_data(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_vehicle_state: AsyncMock,
) -> None:
    """Test that restored data is cleared when coordinator provides fresh data."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    entity_id = "sensor.test_2"
    assert hass.states.get(entity_id).state == "77"

    # Vehicle goes offline, reload to trigger restore
    mock_vehicle_data.side_effect = VehicleOffline

    with patch("homeassistant.components.tesla_fleet.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)

    assert hass.states.get(entity_id).state == "77"

    # Vehicle wakes up with fresh data showing updated value
    mock_vehicle_data.side_effect = None
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    mock_vehicle_state.return_value = {"response": {"state": "online"}, "error": None}
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Should now use fresh coordinator data (battery_level from ALT fixture)
    state = hass.states.get(entity_id)
    assert state.state != STATE_UNAVAILABLE
    assert state.state != STATE_UNKNOWN


async def test_sensor_no_restored_data_shows_unknown(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_vehicle_state: AsyncMock,
) -> None:
    """Test that sensor without restored data shows unknown when vehicle is asleep."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Start with vehicle asleep from the beginning (no prior data to restore)
    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    mock_vehicle_data.side_effect = VehicleOffline

    await setup_platform(hass, normal_config_entry, [Platform.SENSOR])

    entity_id = "sensor.test_2"
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNKNOWN
