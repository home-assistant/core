"""Test the Tessie sensor platform."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import TEST_VEHICLE_STATE_ONLINE, assert_entities, setup_platform

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Tests that the sensor entities are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_charge_energy_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_get_state: AsyncMock,
) -> None:
    """Test reset detection for charge energy sensor."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Initial fixture has charge_energy_added = 18.47
    await setup_platform(hass, [Platform.SENSOR])
    entity_id = "sensor.test_charge_energy_added"

    state = hass.states.get(entity_id)
    assert state.state == "18.47"
    assert state.attributes.get("last_reset") is None

    # Small correction should NOT trigger reset
    correction_data = deepcopy(TEST_VEHICLE_STATE_ONLINE)
    correction_data["charge_state"]["charge_energy_added"] = 18.0
    mock_get_state.return_value = correction_data
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "18.0"
    assert state.attributes.get("last_reset") is None

    # Drop to 0 should trigger reset
    freezer.move_to("2024-01-01 01:00:00+00:00")
    reset_data = deepcopy(TEST_VEHICLE_STATE_ONLINE)
    reset_data["charge_state"]["charge_energy_added"] = 0
    mock_get_state.return_value = reset_data
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "0"
    assert state.attributes.get("last_reset") is not None

    # Large drop (> 1 kWh) should trigger reset
    increase_data = deepcopy(TEST_VEHICLE_STATE_ONLINE)
    increase_data["charge_state"]["charge_energy_added"] = 20.0
    mock_get_state.return_value = increase_data
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.move_to("2024-01-01 02:00:00+00:00")
    drop_data = deepcopy(TEST_VEHICLE_STATE_ONLINE)
    drop_data["charge_state"]["charge_energy_added"] = 5.0
    mock_get_state.return_value = drop_data
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "5.0"
    assert state.attributes.get("last_reset") is not None


async def test_charge_energy_restore_last_reset(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_get_state: AsyncMock,
) -> None:
    """Test that last_reset is restored after a reload."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    # Initial fixture has charge_energy_added = 18.47
    entry = await setup_platform(hass, [Platform.SENSOR])
    entity_id = "sensor.test_charge_energy_added"

    # Trigger a reset by dropping to 0
    freezer.move_to("2024-01-01 01:00:00+00:00")
    reset_data = deepcopy(TEST_VEHICLE_STATE_ONLINE)
    reset_data["charge_state"]["charge_energy_added"] = 0
    mock_get_state.return_value = reset_data
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    last_reset = state.attributes["last_reset"]
    assert last_reset is not None

    # Reload the entry
    mock_get_state.return_value = TEST_VEHICLE_STATE_ONLINE
    with patch("homeassistant.components.tessie.PLATFORMS", [Platform.SENSOR]):
        assert await hass.config_entries.async_reload(entry.entry_id)

    # last_reset should be restored
    state = hass.states.get(entity_id)
    assert state.attributes["last_reset"] == last_reset
