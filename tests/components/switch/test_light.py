"""The tests for the Light Switch platform."""

from homeassistant.setup import async_setup_component


async def test_default_state(hass):
    """Test light switch yaml config."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "switch",
                "entity_id": "switch.test",
                "name": "Christmas Tree Lights",
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.christmas_tree_lights")


async def test_default_state_no_name(hass):
    """Test light switch default name."""
    await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "switch",
                "entity_id": "switch.test",
            }
        },
    )
    await hass.async_block_till_done()

    assert hass.states.get("light.light_switch")
