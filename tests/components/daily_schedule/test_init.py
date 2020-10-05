"""The tests for the daily schedule integration."""
from homeassistant.components.daily_schedule.const import (
    ATTR_END,
    ATTR_SCHEDULE,
    ATTR_START,
    DOMAIN,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_change_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    entity_id = f"{Platform.BINARY_SENSOR}.my_test"
    config_entry = MockConfigEntry(domain=DOMAIN, title="My Test", unique_id="1234")

    # Add the config entry.
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry.
    registry = er.async_get(hass)
    assert registry.async_get(entity_id) is not None
    state = hass.states.get(entity_id)
    assert state.state == "off"
    assert state.attributes[ATTR_SCHEDULE] == []

    # Update the config entry.
    hass.config_entries.async_update_entry(
        config_entry,
        options={ATTR_SCHEDULE: [{ATTR_START: "00:00:00", ATTR_END: "00:00:00"}]},
    )
    await hass.async_block_till_done()

    # Check the updated entity.
    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes[ATTR_SCHEDULE] == [
        {ATTR_START: "00:00:00", ATTR_END: "00:00:00"},
    ]

    # Remove the config entry.
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed.
    assert hass.states.get(entity_id) is None
    assert registry.async_get(entity_id) is None
