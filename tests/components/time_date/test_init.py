"""Test the Time & Date integration."""
from homeassistant.components.time_date.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_and_remove_config_entry(hass: HomeAssistant) -> None:
    """Test setting up and removing a config entry."""
    registry = er.async_get(hass)
    time_utc_entity_id = "sensor.time_utc"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "beat": False,
            "date": False,
            "date_time": False,
            "date_time_iso": False,
            "date_time_utc": False,
            "time": False,
            "time_date": False,
            "time_utc": True,
        },
        title="Time & Date",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(time_utc_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(time_utc_entity_id)
    assert state.state
    assert state.attributes

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(time_utc_entity_id) is None
    assert registry.async_get(time_utc_entity_id) is None
