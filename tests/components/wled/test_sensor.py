"""Tests for the WLED sensor platform."""
from homeassistant.components.wled.const import (
    ATTR_LED_COUNT,
    ATTR_MAX_POWER,
    CURRENT_MA,
    DATA_BYTES,
    TIME_SECONDS,
)
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant

from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the WLED sensors."""
    await init_integration(hass, aioclient_mock)
    await hass.async_block_till_done()

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.wled_light_estimated_current")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:power"
    assert state.attributes.get(ATTR_LED_COUNT) == 30
    assert state.attributes.get(ATTR_MAX_POWER) == 850
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == CURRENT_MA
    assert state.state == "470"

    entry = entity_registry.async_get("sensor.wled_light_estimated_current")
    assert entry
    assert entry.unique_id == "wled_aabbccddeeff_sensor_estimated_current"

    state = hass.states.get("sensor.wled_light_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == TIME_SECONDS
    assert state.state == "32"

    entry = entity_registry.async_get("sensor.wled_light_uptime")
    assert entry
    assert entry.unique_id == "wled_aabbccddeeff_sensor_uptime"

    state = hass.states.get("sensor.wled_light_free_memory")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:memory"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == DATA_BYTES
    assert state.state == "14600"

    entry = entity_registry.async_get("sensor.wled_light_free_memory")
    assert entry
    assert entry.unique_id == "wled_aabbccddeeff_sensor_free_heap"
