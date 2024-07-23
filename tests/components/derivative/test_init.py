"""Test the Derivative integration."""

import pytest

from homeassistant.components.derivative.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ["sensor"])
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    derivative_entity_id = f"{platform}.my_derivative"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "My derivative",
            "round": 1.0,
            "source": "sensor.input",
            "time_window": {"seconds": 0.0},
            "unit_prefix": "k",
            "unit_time": "min",
        },
        title="My derivative",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(derivative_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(derivative_entity_id)
    assert state.state == "0"
    assert "unit_of_measurement" not in state.attributes
    assert state.attributes["source"] == "sensor.input"

    hass.states.async_set(input_sensor_entity_id, 10, {"unit_of_measurement": "dog"})
    hass.states.async_set(input_sensor_entity_id, 11, {"unit_of_measurement": "dog"})
    await hass.async_block_till_done()
    state = hass.states.get(derivative_entity_id)
    assert state.state != "0"
    assert state.attributes["unit_of_measurement"] == "kdog/min"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(derivative_entity_id) is None
    assert entity_registry.async_get(derivative_entity_id) is None
