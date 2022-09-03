"""Test the Utility Cost integration."""
import pytest

from homeassistant.components.utility_cost.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    utility_input_sensor_entity_id = "sensor.utility_input"
    price_input_sensor_entity_id = "sensor.price_input"
    registry = er.async_get(hass)
    utility_cost_entity_id = f"{platform}.my_utility_cost"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My utility cost",
            "utility_source": "sensor.utility_input",
            "price_source": "sensor.price_input",
        },
        title="My utility cost",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(utility_cost_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(utility_cost_entity_id)
    assert state.state == "unknown"
    assert "unit_of_measurement" not in state.attributes
    assert state.attributes["utility_source"] == "sensor.utility_input"
    assert state.attributes["price_source"] == "sensor.price_input"

    hass.states.async_set(
        price_input_sensor_entity_id, 20, {"unit_of_measurement": "EUR/cat"}
    )
    await hass.async_block_till_done()
    hass.states.async_set(
        utility_input_sensor_entity_id,
        10,
        {"unit_of_measurement": "cat", "state_class": "total"},
    )
    hass.states.async_set(
        utility_input_sensor_entity_id,
        11,
        {"unit_of_measurement": "cat", "state_class": "total"},
    )
    await hass.async_block_till_done()

    state = hass.states.get(utility_cost_entity_id)
    assert state.state != "unknown"
    assert state.attributes["unit_of_measurement"] == "EUR"
    assert state.attributes["last_period"] == "0"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(utility_cost_entity_id) is None
    assert registry.async_get(utility_cost_entity_id) is None
