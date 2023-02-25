"""Test the Lifetime Total integration."""

from homeassistant.components.lifetime_total.const import DOMAIN
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    registry = er.async_get(hass)
    lifetime_total_entity_id = "sensor.my_lifetime_total"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor_entity_id,
            "name": "My lifetime_total",
        },
        title="My lifetime_total",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(lifetime_total_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(lifetime_total_entity_id)
    assert state.state == "0.0"
    assert state.attributes == {
        ATTR_FRIENDLY_NAME: "My lifetime_total",
        "last_reading": 0.0,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    }

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(lifetime_total_entity_id) is None
    assert registry.async_get(lifetime_total_entity_id) is None
