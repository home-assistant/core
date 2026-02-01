"""Test the photoptimizer integration."""

import pytest

from homeassistant.components.photoptimizer.const import DOMAIN
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
    photoptimizer_entity_id = f"{platform}.my_photoptimizer"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor_entity_id,
            "name": "My photoptimizer",
        },
        title="My photoptimizer",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert entity_registry.async_get(photoptimizer_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(photoptimizer_entity_id)
    assert state.state == "unknown"
    assert state.attributes == {}

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(photoptimizer_entity_id) is None
    assert entity_registry.async_get(photoptimizer_entity_id) is None
