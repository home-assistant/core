"""Tests for the Modern Forms fan platform."""
from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_PERCENTAGE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.modern_forms.const import (
    ATTR_SLEEP_TIME,
    DOMAIN,
    SERVICE_CLEAR_FAN_SLEEP_TIMER,
    SERVICE_SET_FAN_SLEEP_TIMER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.components.modern_forms import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_fan_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Modern Forms fans."""
    await init_integration(hass, aioclient_mock)

    entity_registry = er.async_get(hass)

    state = hass.states.get("fan.modernformsfan_fan")
    assert state
    assert state.attributes.get(ATTR_PERCENTAGE) == 50
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_FORWARD
    assert state.state == STATE_ON

    entry = entity_registry.async_get("fan.modernformsfan_fan")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"


async def test_change_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the change of state of the Modern Forms fan."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(
            on=False,
        )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PERCENTAGE: 100,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(on=True, speed=6)


async def test_sleep_timer_services(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan", ATTR_SLEEP_TIME: 1},
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(sleep=60)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_FAN_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(sleep=0)


async def test_change_direction(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_DIRECTION,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_DIRECTION: DIRECTION_REVERSE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(
            direction=DIRECTION_REVERSE,
        )


async def test_set_percentage(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test the change of percentage for the Modern Forms fan."""
    await init_integration(hass, aioclient_mock)
    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PERCENTAGE: 100,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(
            on=True,
            speed=6,
        )

    await init_integration(hass, aioclient_mock)
    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PERCENTAGE,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PERCENTAGE: 0,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(on=False)


async def test_fan_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test error handling of the Modern Forms fans."""

    await init_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    aioclient_mock.post("http://192.168.1.123:80/mf", text="", status=400)

    with patch("homeassistant.components.modern_forms.ModernFormsDevice.update"):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        state = hass.states.get("fan.modernformsfan_fan")
        assert state.state == STATE_ON
        assert "Invalid response from API" in caplog.text


async def test_fan_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Moder Forms fans."""
    await init_integration(hass, aioclient_mock)

    with patch("homeassistant.components.modern_forms.ModernFormsDevice.update"), patch(
        "homeassistant.components.modern_forms.ModernFormsDevice.fan",
        side_effect=ModernFormsConnectionError,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("fan.modernformsfan_fan")
        assert state.state == STATE_UNAVAILABLE
