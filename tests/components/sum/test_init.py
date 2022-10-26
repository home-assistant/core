"""Test the Sum integration."""
from __future__ import annotations

import pytest

from homeassistant.components.sum.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from . import SUM_VALUE, VALUES

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    registry = er.async_get(hass)
    sum_entity_id = f"{platform}.my_sum"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": input_sensors,
            "name": "My sum",
            "round_digits": 2.0,
        },
        title="My sum",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(sum_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(sum_entity_id)
    assert state.state == "30.0"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(sum_entity_id) is None
    assert registry.async_get(sum_entity_id) is None


async def test_sum_sensor_from_yaml(hass: HomeAssistant) -> None:
    """Test the sum sensor setup from integration yaml."""
    config = {
        "sum": [
            {
                "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
                "unique_id": "very_unique_id",
                "name": "My Sum",
            },
            {
                "entity_ids": ["sensor.test_1", "sensor.test_3"],
                "unique_id": "very_unique_id2",
                "name": "My Sum2",
            },
        ]
    }

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()

    entity_ids = config["sum"][0]["entity_ids"]

    for entity_id, value in dict(zip(entity_ids, VALUES)).items():
        hass.states.async_set(entity_id, value)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.my_sum")
    state2 = hass.states.get("sensor.my_sum2")

    assert str(float(SUM_VALUE)) == state.state
    assert str(float(sum([VALUES[0], VALUES[2]]))) == state2.state


async def test_sum_sensor_from_yaml_no_config(hass: HomeAssistant) -> None:
    """Test the sum sensor setup from integration yaml with missing config."""
    assert await async_setup_component(hass, DOMAIN, {"sum": None})
    await hass.async_block_till_done()

    entities = er.async_get(hass)
    assert entities.entities == {}
