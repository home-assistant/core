"""Tests for glances sensors."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.glances.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import parse_datetime

from . import MOCK_REFERENCE_DATE, MOCK_USER_INPUT

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensor states are correctly collected from library."""

    freezer.move_to(MOCK_REFERENCE_DATE)

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )


async def test_uptime_variation(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test uptime small variation update."""

    # Init with reference time
    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    uptime_state = hass.states.get("sensor.0_0_0_0_uptime").state

    # Small time change should not change uptime
    freezer.tick(delta=timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    uptime_state2 = hass.states.get("sensor.0_0_0_0_uptime").state
    assert uptime_state2 == uptime_state

    # Large time change should change uptime
    freezer.tick(delta=timedelta(minutes=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    uptime_state3 = hass.states.get("sensor.0_0_0_0_uptime").state
    assert uptime_state3 != uptime_state
    assert parse_datetime(uptime_state3) == parse_datetime(uptime_state) + timedelta(
        minutes=60, seconds=60
    )
