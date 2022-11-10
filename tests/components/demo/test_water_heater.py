"""The tests for the demo water_heater component."""
import pytest
import voluptuous as vol

from homeassistant.components import water_heater
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from tests.components.water_heater import common

ENTITY_WATER_HEATER = "water_heater.demo_water_heater"
ENTITY_WATER_HEATER_CELSIUS = "water_heater.demo_water_heater_celsius"


@pytest.fixture(autouse=True)
async def setup_comp(hass):
    """Set up demo component."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert await async_setup_component(
        hass, water_heater.DOMAIN, {"water_heater": {"platform": "demo"}}
    )
    await hass.async_block_till_done()


async def test_setup_params(hass):
    """Test the initial parameters."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 119
    assert state.attributes.get("operation_mode") == "on"
    assert state.attributes.get("preset_mode") == "eco"


async def test_default_setup_params(hass):
    """Test the setup with default parameters."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("min_temp") == 110
    assert state.attributes.get("max_temp") == 140


async def test_set_only_target_temp_bad_attr(hass):
    """Test setting the target temperature without required attribute."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 119
    with pytest.raises(vol.Invalid):
        await common.async_set_temperature(hass, None, ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 119


async def test_set_only_target_temp(hass):
    """Test the setting of the target temperature."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 119
    await common.async_set_temperature(hass, 110, ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 110


async def test_set_operation_bad_attr_and_state(hass):
    """Test setting operation mode without required attribute.

    Also check the state.
    """
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "eco"
    assert state.state == "on"
    with pytest.raises(vol.Invalid):
        await common.async_set_operation_mode(hass, None, ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "eco"
    assert state.state == "on"


async def test_set_operation(hass):
    """Test setting of new operation mode."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("operation_mode") == "on"
    assert state.state == "on"
    await common.async_set_operation_mode(hass, "boost", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("operation_mode") == "boost"
    assert state.state == "boost"


async def test_set_preset_mode_bad_attr(hass):
    """Test setting the away mode without required attribute."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "eco"
    with pytest.raises(vol.Invalid):
        await common.async_set_preset_mode(hass, None, ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "eco"


async def test_set_preset_mode(hass):
    """Test setting the away mode on/true."""
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "eco"
    await common.async_set_preset_mode(hass, "normal", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("preset_mode") == "normal"


async def test_set_only_target_temp_with_convert(hass):
    """Test the setting of the target temperature."""
    state = hass.states.get(ENTITY_WATER_HEATER_CELSIUS)
    assert state.attributes.get("temperature") == 113
    await common.async_set_temperature(hass, 114, ENTITY_WATER_HEATER_CELSIUS)
    state = hass.states.get(ENTITY_WATER_HEATER_CELSIUS)
    assert state.attributes.get("temperature") == 114
