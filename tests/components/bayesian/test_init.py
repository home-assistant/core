"""Test the Bayesian integration."""
import pytest

from homeassistant.components.bayesian.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    input_sensor_entity_id = "sensor.input"
    registry = er.async_get(hass)
    bayesian_entity_id = f"{platform}.my_bayesian"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_id": input_sensor_entity_id,
            "name": "My bayesian",
        },
        title="My bayesian",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(bayesian_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(bayesian_entity_id)
    # TODO Check the state of the entity has changed as expected
    assert state.state == "unknown"
    assert state.attributes == {}

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(bayesian_entity_id) is None
    assert registry.async_get(bayesian_entity_id) is None
