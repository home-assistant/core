"""Light tests for the Skybell integration."""
from datetime import timedelta

from aioskybell.helpers.const import BASE_URL

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_SUPPORTED_COLOR_MODES,
    DOMAIN as DOMAIN,
    ColorMode,
)
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import DEVICE_ID, async_init_integration, set_aioclient_responses

from tests.common import async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_light_state(hass: HomeAssistant, connection) -> None:
    """Test we get light data."""
    await async_init_integration(hass)
    state = hass.states.get("light.front_door")
    assert state.state == STATE_OFF
    assert dict(state.attributes) == {
        ATTR_ATTRIBUTION: "Data provided by Skybell.com",
        ATTR_FRIENDLY_NAME: "Front door",
        ATTR_SUPPORTED_COLOR_MODES: [ColorMode.RGB],
        ATTR_SUPPORTED_FEATURES: 0,
    }


async def test_light_service_calls(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, connection
) -> None:
    """Test we get expected results from service calls."""
    await async_init_integration(hass)
    aioclient_mock.patch(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        json={},
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_RGB_COLOR: [10, 125, 255], ATTR_BRIGHTNESS: 127},
        target={ATTR_ENTITY_ID: "light.front_door"},
        blocking=True,
    )
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        text=load_fixture("skybell/device_settings_change.json"),
    )
    await set_aioclient_responses(aioclient_mock)
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get("light.front_door")
    assert state.state == STATE_ON
    assert state.attributes[ATTR_BRIGHTNESS] == 127
    aioclient_mock.patch(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        json={},
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        target={ATTR_ENTITY_ID: "light.front_door"},
        blocking=True,
    )
    aioclient_mock.clear_requests()
    await set_aioclient_responses(aioclient_mock)
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get("light.front_door")
    assert state.state == STATE_OFF
