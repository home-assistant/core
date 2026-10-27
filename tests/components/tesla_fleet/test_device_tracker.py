"""Test the Tesla Fleet device tracker platform."""

from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.exceptions import VehicleOffline

from homeassistant.components.tesla_fleet.coordinator import VEHICLE_INTERVAL
from homeassistant.const import STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, setup_platform
from .const import VEHICLE_ASLEEP


async def test_device_tracker(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the device tracker entities are correct."""

    await setup_platform(hass, normal_config_entry, [Platform.DEVICE_TRACKER])
    assert_entities(hass, normal_config_entry.entry_id, entity_registry, snapshot)


async def test_device_tracker_offline(
    hass: HomeAssistant,
    mock_vehicle_data: AsyncMock,
    normal_config_entry: MockConfigEntry,
) -> None:
    """Tests that the device tracker entities are correct when offline."""

    mock_vehicle_data.side_effect = VehicleOffline
    await setup_platform(hass, normal_config_entry, [Platform.DEVICE_TRACKER])
    state = hass.states.get("device_tracker.test_location")
    assert state.state == STATE_UNKNOWN


async def test_device_tracker_restore_kept_while_asleep(
    hass: HomeAssistant,
    normal_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_state: AsyncMock,
) -> None:
    """Test a restored location stays through polls while the vehicle sleeps."""

    await setup_platform(hass, normal_config_entry, [Platform.DEVICE_TRACKER])
    before = hass.states.get("device_tracker.test_location").state
    assert before != STATE_UNKNOWN

    mock_vehicle_state.return_value = VEHICLE_ASLEEP
    with patch(
        "homeassistant.components.tesla_fleet.PLATFORMS", [Platform.DEVICE_TRACKER]
    ):
        assert await hass.config_entries.async_reload(normal_config_entry.entry_id)
    assert hass.states.get("device_tracker.test_location").state == before

    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("device_tracker.test_location").state == before
