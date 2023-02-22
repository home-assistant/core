"""Test the Min/Max integration."""
import pytest

from homeassistant.components.attribute_sensor.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("sensor",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    hass.states.async_set(
        "sensor.sensor_one", 50, {"attribute1": 75, "attribute2": 100}
    )

    registry = er.async_get(hass)
    attribute_sensor_entity_id = f"{platform}.test_attribute_sensor"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "name": "test_attribute_sensor",
            "source": "sensor.sensor_one",
            "attribute": "attribute1",
        },
        title="My attribute sensor",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(attribute_sensor_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(attribute_sensor_entity_id)
    assert state.state == 75

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(attribute_sensor_entity_id) is None
    assert registry.async_get(attribute_sensor_entity_id) is None
