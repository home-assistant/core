"""Test the Generic thermostat precision functionality."""
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.components.climate import common
from tests.components.generic_thermostat.const import ENTITY


async def test_precision(hass: HomeAssistant, setup_comp_9) -> None:
    """Test that setting precision to tenths works as intended."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    await common.async_set_temperature(hass, 23.27)
    state = hass.states.get(ENTITY)
    assert state.attributes.get("temperature") == 23.3
    # check that target_temp_step defaults to precision
    assert state.attributes.get("target_temp_step") == 0.1
