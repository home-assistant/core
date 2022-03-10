"""The test for the min/max init."""
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONFIG = {
    "entity_ids": ["sensor.test_1", "sensor.test_2", "sensor.test_3"],
    "name": "Max sensor",
    "round_digits": 2,
    "type": "max",
}


async def test_min_max_load_and_unload(hass: HomeAssistant) -> None:
    """Test loading and unloading min/max entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONFIG, unique_id="test")
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(Platform.SENSOR)) == 1

    assert await config_entry.async_unload(hass)
    await hass.async_block_till_done()
    entities = hass.states.async_entity_ids(Platform.SENSOR)
    assert len(entities) == 1
    for entity in entities:
        assert hass.states.get(entity).state == STATE_UNAVAILABLE
