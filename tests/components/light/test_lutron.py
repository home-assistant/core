"""The tests for the Lutron Light platform."""

from homeassistant.setup import async_setup_component
from tests.components.light import common
from homeassistant.components.light.lutron import (
    to_hass_level, to_lutron_level, setup_platform
)


async def test_to_lutron_level(hass):
    """Test to_lutron_level()"""
    level = 128
    assert round(to_lutron_level(level), 1) == 50.2


async def test_to_hass_level(hass):
    """Test to_hass_level()"""
    level = 50.2
    assert to_hass_level(level) == 128


async def test_default_state(hass):
    """Test lutron light default state."""
    setup_platform(hass, 'light', {'lutron': {
        'platform': 'lutron', 'entity_id': 'switch.test',
        'name': 'Christmas Tree Lights'
    }})
    await hass.async_block_till_done()

    state = hass.states.get('light.christmas_tree_lights')
    assert state is not None
    assert state.state == 'unavailable'
    assert state.attributes['supported_features'] == 0
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('hs_color') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('effect_list') is None
    assert state.attributes.get('effect') is None
