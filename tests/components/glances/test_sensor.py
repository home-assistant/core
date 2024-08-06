"""Tests for glances sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from syrupy import SnapshotAssertion

from homeassistant.components.glances.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import HA_SENSOR_DATA, MOCK_REFERENCE_DATE, MOCK_USER_INPUT

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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_api: AsyncMock
) -> None:
    """Test uptime small variation update."""

    # Init with reference time
    freezer.move_to(MOCK_REFERENCE_DATE)
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    uptime_state = hass.states.get("sensor.0_0_0_0_uptime").state

    # Time change should not change uptime (absolute date)
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    uptime_state2 = hass.states.get("sensor.0_0_0_0_uptime").state
    assert uptime_state2 == uptime_state

    mock_data = HA_SENSOR_DATA.copy()
    mock_data["uptime"] = "1:25:20"
    mock_api.return_value.get_ha_sensor_data = AsyncMock(return_value=mock_data)

    # Server has been restarted so therefore we should have a new state
    freezer.move_to(MOCK_REFERENCE_DATE + timedelta(days=2))
    freezer.tick(delta=timedelta(seconds=120))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.0_0_0_0_uptime").state == "2024-02-15T12:49:52+00:00"
