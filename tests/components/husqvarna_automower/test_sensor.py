"""Tests for switch platform."""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aioautomower.model import MowerModes
from aioautomower.utils import mower_list_to_dictionary_dataclass
from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_json_value_fixture,
)

TEST_MOWER_ID = "c7233734-b219-4287-a173-08e3643f89f0"


async def test_sensor_unknown_states(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a sensor which returns unknown."""
    values = mower_list_to_dictionary_dataclass(
        load_json_value_fixture("mower.json", DOMAIN)
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("sensor.test_mower_1_mode")
    assert state is not None
    assert state.state == "main_area"

    values[TEST_MOWER_ID].mower.mode = MowerModes.UNKNOWN
    mock_automower_client.get_status.return_value = values
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.test_mower_1_mode")
    assert state.state == "unknown"


async def test_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states of the sensors."""
    with patch(
        "homeassistant.components.husqvarna_automower.PLATFORMS",
        [Platform.SENSOR],
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
