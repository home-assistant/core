"""The tests for SleepIQ light platform."""
from homeassistant.components.light import DOMAIN
from homeassistant.components.sleepiq.coordinator import LONGER_UPDATE_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed
from tests.components.sleepiq.conftest import (
    BED_ID,
    BED_NAME,
    BED_NAME_LOWER,
    setup_platform,
)


async def test_setup(hass, mock_asyncsleepiq):
    """Test for successfully setting up the SleepIQ platform."""
    entry = await setup_platform(hass, DOMAIN)
    entity_registry = er.async_get(hass)

    assert len(entity_registry.entities) == 2

    entry = entity_registry.async_get(f"light.sleepnumber_{BED_NAME_LOWER}_light_1")
    assert entry
    assert entry.original_name == f"SleepNumber {BED_NAME} Light 1"
    assert entry.unique_id == f"{BED_ID}-light-1"

    entry = entity_registry.async_get(f"light.sleepnumber_{BED_NAME_LOWER}_light_2")
    assert entry
    assert entry.original_name == f"SleepNumber {BED_NAME} Light 2"
    assert entry.unique_id == f"{BED_ID}-light-2"


async def test_light_set_states(hass, mock_asyncsleepiq):
    """Test light change."""
    await setup_platform(hass, DOMAIN)

    await hass.services.async_call(
        DOMAIN,
        "turn_on",
        {ATTR_ENTITY_ID: f"light.sleepnumber_{BED_NAME_LOWER}_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].foundation.lights[0].turn_on.assert_called_once()

    await hass.services.async_call(
        DOMAIN,
        "turn_off",
        {ATTR_ENTITY_ID: f"light.sleepnumber_{BED_NAME_LOWER}_light_1"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_asyncsleepiq.beds[BED_ID].foundation.lights[0].turn_off.assert_called_once()


async def test_switch_get_states(hass, mock_asyncsleepiq):
    """Test light update."""
    await setup_platform(hass, DOMAIN)

    assert (
        hass.states.get(f"light.sleepnumber_{BED_NAME_LOWER}_light_1").state
        == STATE_OFF
    )
    mock_asyncsleepiq.beds[BED_ID].foundation.lights[0].is_on = True

    async_fire_time_changed(hass, utcnow() + LONGER_UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (
        hass.states.get(f"light.sleepnumber_{BED_NAME_LOWER}_light_1").state == STATE_ON
    )
