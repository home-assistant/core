"""Tests for the WLED sensor platform."""
from datetime import datetime

from asynctest import patch

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.wled.const import (
    ATTR_LED_COUNT,
    ATTR_MAX_POWER,
    CURRENT_MA,
    DOMAIN,
)
from homeassistant.const import ATTR_ICON, ATTR_UNIT_OF_MEASUREMENT, DATA_BYTES
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.components.wled import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the WLED sensors."""

    entry = await init_integration(hass, aioclient_mock, skip_setup=True)
    registry = await hass.helpers.entity_registry.async_get_registry()

    # Pre-create registry entries for disabled by default sensors
    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_uptime",
        suggested_object_id="wled_rgb_light_uptime",
        disabled_by=None,
    )

    registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "aabbccddeeff_free_heap",
        suggested_object_id="wled_rgb_light_free_memory",
        disabled_by=None,
    )

    # Setup
    test_time = datetime(2019, 11, 11, 9, 10, 32, tzinfo=dt_util.UTC)
    with patch("homeassistant.components.wled.sensor.utcnow", return_value=test_time):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.wled_rgb_light_estimated_current")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:power"
    assert state.attributes.get(ATTR_LED_COUNT) == 30
    assert state.attributes.get(ATTR_MAX_POWER) == 850
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == CURRENT_MA
    assert state.state == "470"

    entry = registry.async_get("sensor.wled_rgb_light_estimated_current")
    assert entry
    assert entry.unique_id == "aabbccddeeff_estimated_current"

    state = hass.states.get("sensor.wled_rgb_light_uptime")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:clock-outline"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) is None
    assert state.state == "2019-11-11T09:10:00+00:00"

    entry = registry.async_get("sensor.wled_rgb_light_uptime")
    assert entry
    assert entry.unique_id == "aabbccddeeff_uptime"

    state = hass.states.get("sensor.wled_rgb_light_free_memory")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:memory"
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == DATA_BYTES
    assert state.state == "14600"

    entry = registry.async_get("sensor.wled_rgb_light_free_memory")
    assert entry
    assert entry.unique_id == "aabbccddeeff_free_heap"


async def test_disabled_by_default_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the disabled by default WLED sensors."""
    await init_integration(hass, aioclient_mock)
    registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("sensor.wled_rgb_light_uptime")
    assert state is None

    entry = registry.async_get("sensor.wled_rgb_light_uptime")
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"

    state = hass.states.get("sensor.wled_rgb_light_free_memory")
    assert state is None

    entry = registry.async_get("sensor.wled_rgb_light_free_memory")
    assert entry
    assert entry.disabled
    assert entry.disabled_by == "integration"
