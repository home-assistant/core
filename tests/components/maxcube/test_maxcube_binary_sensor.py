"""Test EQ3 Max! Window Shutters."""
from datetime import timedelta

from maxcube.cube import MaxCube
from maxcube.windowshutter import MaxWindowShutter

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import utcnow

from tests.common import async_fire_time_changed

ENTITY_ID = "binary_sensor.testroom_testshutter"
BATTERY_ENTITY_ID = f"{ENTITY_ID}_battery"


async def test_window_shuttler(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    cube: MaxCube,
    windowshutter: MaxWindowShutter,
) -> None:
    """Test a successful setup with a shuttler device."""
    assert entity_registry.async_is_registered(ENTITY_ID)
    entity = entity_registry.async_get(ENTITY_ID)
    assert entity.unique_id == "AABBCCDD03"
    assert entity.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "TestRoom TestShutter"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.WINDOW

    windowshutter.is_open = False
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == STATE_OFF


async def test_window_shuttler_battery(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    cube: MaxCube,
    windowshutter: MaxWindowShutter,
) -> None:
    """Test battery binary_state with a shuttler device."""
    assert entity_registry.async_is_registered(BATTERY_ENTITY_ID)
    entity = entity_registry.async_get(BATTERY_ENTITY_ID)
    assert entity.unique_id == "AABBCCDD03_battery"
    assert entity.entity_category == EntityCategory.DIAGNOSTIC

    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state is not None
    assert state.attributes.get(ATTR_DEVICE_CLASS) == BinarySensorDeviceClass.BATTERY
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "TestRoom TestShutter battery"

    windowshutter.battery = 1  # maxcube-api MAX_DEVICE_BATTERY_LOW
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state.state == STATE_ON  # on means low

    windowshutter.battery = 0  # maxcube-api MAX_DEVICE_BATTERY_OK
    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    state = hass.states.get(BATTERY_ENTITY_ID)
    assert state.state == STATE_OFF  # off means normal
