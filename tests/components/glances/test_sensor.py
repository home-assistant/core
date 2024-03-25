"""Tests for glances sensors."""

from datetime import timedelta

from freezegun.api import freeze_time
from syrupy import SnapshotAssertion

from homeassistant.components.glances import GlancesDataUpdateCoordinator
from homeassistant.components.glances.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_REFERENCE_DATE, MOCK_USER_INPUT

from tests.common import MockConfigEntry


async def test_sensor_states(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test sensor states are correctly collected from library."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    with freeze_time(MOCK_REFERENCE_DATE):
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
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test uptime small variation update."""

    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, entry_id="test")
    entry.add_to_hass(hass)

    # Setup with expected timestamp for reference
    with freeze_time(MOCK_REFERENCE_DATE):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    uptime_state = hass.states.get("sensor.0_0_0_0_uptime").state

    coordinator: GlancesDataUpdateCoordinator = hass.data[DOMAIN]["test"]

    # Expected timestamp + 60s => uptime should not change
    with freeze_time(MOCK_REFERENCE_DATE + timedelta(seconds=60)):
        await coordinator._async_update_data()
        await hass.async_block_till_done()
        uptime_state2 = hass.states.get("sensor.0_0_0_0_uptime").state
        assert uptime_state == uptime_state2

    # Expected timestamp + 60min => uptime should change
    with freeze_time(MOCK_REFERENCE_DATE + timedelta(minutes=60)):
        await coordinator._async_update_data()
        await hass.async_block_till_done()
        uptime_state3 = hass.states.get("sensor.0_0_0_0_uptime").state
        assert uptime_state != uptime_state3
