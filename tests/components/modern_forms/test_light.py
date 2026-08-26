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
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration, init_integration_gen4

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
) -> None:
    """Test error handling of the Modern Forms lights."""

    await init_integration(hass, aioclient_mock)
    aioclient_mock.clear_requests()

    aioclient_mock.post("http://192.168.1.123:80/mf", text="", status=400)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_response"


async def test_light_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Modern Forms lights."""
    await init_integration(hass, aioclient_mock)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.light",
            side_effect=ModernFormsConnectionError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_light"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"

    state = hass.states.get("light.modernformsfan_light")
    assert state.state == STATE_UNAVAILABLE


async def test_light_state_gen4(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test a multi-fixture Gen4 fan creates one light entity per fixture."""
    await init_integration_gen4(hass, aioclient_mock)

    state = hass.states.get("light.modernformsfan_uplight")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Uplight"
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.modernformsfan_uplight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_2"

    state = hass.states.get("light.modernformsfan_downlight")
    assert state
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "ModernFormsFan Downlight"
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("light.modernformsfan_downlight")
    assert entry
    assert entry.unique_id == "AA:BB:CC:00:11:22_3"


async def test_light_change_state_gen4(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Gen4 fixture entities control via light_fixture(), not light()."""
    await init_integration_gen4(hass, aioclient_mock)

    with (
        patch("aiomodernforms.ModernFormsDevice.light_fixture") as light_fixture_mock,
        patch("aiomodernforms.ModernFormsDevice.light") as light_mock,
    ):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.modernformsfan_uplight"},
            blocking=True,
        )
        await hass.async_block_till_done()
        light_fixture_mock.assert_called_once_with(2, on=False)
        light_mock.assert_not_called()
