"""Tests for binary sensor platform."""

from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerActivities
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)


async def test_binary_sensor_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test binary sensor states."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("binary_sensor.test_mower_1_charging")
    assert state is not None
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_mower_1_leaving_dock")
    assert state is not None
    assert state.state == "off"
    state = hass.states.get("binary_sensor.test_mower_1_returning_to_dock")
    assert state is not None
    assert state.state == "off"

    for activity, entity in [
        (MowerActivities.CHARGING, "test_mower_1_charging"),
        (MowerActivities.LEAVING, "test_mower_1_leaving_dock"),
        (MowerActivities.GOING_HOME, "test_mower_1_returning_to_dock"),
    ]:
        values[TEST_MOWER_ID].mower.activity = activity
        mock_automower_client.get_status.return_value = values
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        state = hass.states.get(f"binary_sensor.{entity}")
        assert state.state == "on"


async def test_snapshot_binary_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the binary sensors."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ):
        await setup_integration(hass, mock_config_entry)
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        assert entity_entries
        for entity_entry in entity_entries:
            assert hass.states.get(entity_entry.entity_id) == snapshot(
                name=f"{entity_entry.entity_id}-state"
            )
            assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
