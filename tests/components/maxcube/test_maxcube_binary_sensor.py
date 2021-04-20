"""Test EQ3 Max! Window Shutters."""
from datetime import timedelta

from maxcube.cube import MaxCube
from maxcube.windowshutter import MaxWindowShutter

from homeassistant.components.binary_sensor import DEVICE_CLASS_WINDOW
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.helpers import entity_registry as er
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed

ENTITY_ID = "binary_sensor.testroom_testshutter"


async def test_window_shuttler(hass, cube: MaxCube, windowshutter: MaxWindowShutter):
    """Test a successful setup with a shuttler device."""
    entity_registry = er.async_get(hass)
    assert entity_registry.async_is_registered(ENTITY_ID)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == "AABBCCDD03"

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "TestRoom TestShutter"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == DEVICE_CLASS_WINDOW

    windowshutter.is_open = False
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF
