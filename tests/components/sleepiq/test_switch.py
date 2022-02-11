"""The tests for SleepIQ switch platform."""
from homeassistant.components.switch import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as er

from .conftest import setup_platform


async def test_setup(hass, mock_aioresponse):
    """Test for successfully setting up the SleepIQ platform."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    assert len(entity_registry.entities) == 1

    entry = entity_registry.async_get("switch.ile_pause_mode")
    assert entry.original_name == "ILE Pause Mode"


async def test_switch_states(hass, mock_aioresponse):
    """Test button press."""
    await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    entry = entity_registry.async_get("switch.ile_pause_mode")

    await hass.services.async_call(
        DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.ile_pause_mode"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_OFF

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: "switch.ile_pause_mode"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_ON

    await hass.services.async_call(
        DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: "switch.ile_pause_mode"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(entry.entity_id).state == STATE_OFF
