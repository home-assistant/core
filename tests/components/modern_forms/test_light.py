"""Tests for the Modern Forms light platform."""

from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError
import pytest

from homeassistant.components.light import ATTR_BRIGHTNESS, DOMAIN as LIGHT_DOMAIN
from homeassistant.components.modern_forms.const import (
    ATTR_SLEEP_TIME,
    DOMAIN,
    SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
    SERVICE_SET_LIGHT_SLEEP_TIMER,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_FRIENDLY_NAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_light_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and values of the Modern Forms lights."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_light")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 128
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Light"
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.modernformsfan_light")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"


async def test_change_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(
            on=False,
        )

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "light.modernformsfan_light", ATTR_BRIGHTNESS: 255},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(on=True, brightness=100)


async def test_sleep_timer_services(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the change of state of the Modern Forms segments."""
    await init_integration(hass, aioclient_mock)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_light", ATTR_SLEEP_TIME: 1},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(sleep=60)

    with patch("aiomodernforms.ModernFormsDevice.light") as light_mock:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_LIGHT_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_mock.assert_called_once_with(sleep=0)


async def test_light_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the Modern Forms lights."""

    await init_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    aioclient_mock.post("http://192.168.1.123:80/mf", text="", status=400)

    with patch(
        "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()
        state = hass.states.get("light.modernformsfan_light")
        assert state.state == STATE_ON
        assert "Invalid response from API" in caplog.text


async def test_light_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Moder Forms lights."""
    await init_integration(hass, aioclient_mock)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.light",
            side_effect=ModernFormsConnectionError,
        ),
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("light.modernformsfan_light")
        assert state.state == STATE_UNAVAILABLE
