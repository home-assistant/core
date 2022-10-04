"""Switch tests for the Skybell integration."""
from datetime import timedelta
from unittest.mock import patch

from aioskybell.helpers.const import BASE_URL

from homeassistant.components.switch import DOMAIN as DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import (
    DEVICE_ID,
    async_init_integration,
    patch_cache,
    set_aioclient_responses,
)

from tests.common import async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_switch_states(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we get switch data."""
    await set_aioclient_responses(aioclient_mock)
    entry = await async_init_integration(hass, skip_setup=True)
    with patch_cache(), patch(
        "homeassistant.core.Config.path",
        return_value="tests/components/skybell/fixtures/cache.pickle",
    ):
        await hass.config_entries.async_setup(entry.entry_id)

    state = hass.states.get("switch.front_door_do_not_disturb")
    assert state.state == STATE_OFF
    state = hass.states.get("switch.front_door_do_not_ring")
    assert state.state == STATE_OFF
    state = hass.states.get("switch.front_door_motion_sensor")
    assert state.state == STATE_ON

    aioclient_mock.patch(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        json={"motion_policy": "disabled"},
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ["switch.front_door_motion_sensor"]},
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
    state = hass.states.get("switch.front_door_motion_sensor")
    assert state.state == STATE_OFF
    aioclient_mock.patch(
        f"{BASE_URL}devices/{DEVICE_ID}/settings/",
        json={"motion_policy": "call"},
    )
    await hass.services.async_call(
        DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ["switch.front_door_motion_sensor"]},
        blocking=True,
    )
    aioclient_mock.clear_requests()
    await set_aioclient_responses(aioclient_mock)
    next_update = dt_util.utcnow() + timedelta(seconds=30)
    async_fire_time_changed(hass, next_update)
    await hass.async_block_till_done()
    state = hass.states.get("switch.front_door_motion_sensor")
    assert state.state == STATE_ON
