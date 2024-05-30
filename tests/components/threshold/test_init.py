"""Test the Min/Max integration."""

import pytest

from homeassistant.components.threshold.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ["binary_sensor"])
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set("sensor.input", "-10")

    input_sensor = "sensor.input"

    threshold_entity_id = f"{platform}.input_threshold"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor,
            "hysteresis": 0.0,
            "lower": -2.0,
            "name": "Input threshold",
            "upper": None,
        },
        title="Input threshold",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(threshold_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(threshold_entity_id)
    assert state.state == "on"
    assert state.attributes["entity_id"] == input_sensor
    assert state.attributes["hysteresis"] == 0.0
    assert state.attributes["lower"] == -2.0
    assert state.attributes["position"] == "below"
    assert state.attributes["sensor_value"] == -10.0
    assert state.attributes["type"] == "lower"
    assert state.attributes["upper"] is None

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(threshold_entity_id) is None
    assert entity_registry.async_get(threshold_entity_id) is None
