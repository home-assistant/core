"""Test the Times of the Day integration."""
from freezegun import freeze_time

from homeassistant.components.tod.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@freeze_time("2022-03-16 17:37:00", tz_offset=-7)
async def test_setup_and_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    registry = er.async_get(hass)
    tod_entity_id = "binary_sensor.my_tod"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "after_time": "10:00:00",
            "before_time": "18:05:00",
            "name": "My tod",
        },
        title="My tod",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(tod_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(tod_entity_id)
    # Check the state of the entity is as expected
    state = hass.states.get("binary_sensor.my_tod")
    assert state.state == "off"
    assert state.attributes["after"] == "2022-03-16T10:00:00-07:00"
    assert state.attributes["before"] == "2022-03-16T18:05:00-07:00"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(tod_entity_id) is None
    assert registry.async_get(tod_entity_id) is None
