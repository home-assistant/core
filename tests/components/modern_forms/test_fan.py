"""Tests for the Modern Forms fan platform."""

from collections.abc import Callable, Coroutine
from typing import Any
from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError
import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_DIRECTION,
    SERVICE_SET_PERCENTAGE,
    SERVICE_SET_PRESET_MODE,
    FanEntityFeature,
)
from homeassistant.components.modern_forms.const import (
    ATTR_SLEEP_TIME,
    DOMAIN,
    SERVICE_CLEAR_FAN_SLEEP_TIMER,
    SERVICE_SET_FAN_SLEEP_TIMER,
)
from homeassistant.components.modern_forms.fan import (
    PRESET_MODE_BREEZE,
    PRESET_MODE_NORMAL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import (
    init_integration,
    init_integration_gen4,
    modern_forms_breeze_active_call_mock,
    modern_forms_breeze_call_mock,
)

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_fan_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and values of the Modern Forms fans."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("fan.modernformsfan_fan")
    assert state
    assert state.attributes.get(ATTR_PERCENTAGE) == 50
    assert state.attributes.get(ATTR_DIRECTION) == DIRECTION_FORWARD
    assert state.state == STATE_ON

    entry = entity_registry.async_get("fan.modernformsfan_fan")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF"


async def test_change_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
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
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test error handling of the Modern Forms fans."""

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
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_response"


async def test_fan_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Modern Forms fans."""
    await init_integration(hass, aioclient_mock)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.fan",
            side_effect=ModernFormsConnectionError,
        ),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"

    state = hass.states.get("fan.modernformsfan_fan")
    assert state.state == STATE_UNAVAILABLE


async def test_breeze_preset_mode_unsupported(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test fans without breeze hardware expose no preset mode."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("fan.modernformsfan_fan")
    assert state
    assert not (
        state.attributes[ATTR_SUPPORTED_FEATURES] & FanEntityFeature.PRESET_MODE
    )
    assert state.attributes.get(ATTR_PRESET_MODE) is None


@pytest.mark.parametrize(
    ("mock_type", "expected_preset_mode"),
    [
        pytest.param(modern_forms_breeze_call_mock, PRESET_MODE_NORMAL, id="wind_off"),
        pytest.param(
            modern_forms_breeze_active_call_mock, PRESET_MODE_BREEZE, id="wind_on"
        ),
    ],
)
async def test_breeze_preset_mode_state(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_type: Callable[
        [HomeAssistant, str, str, dict[str, Any]],
        Coroutine[Any, Any, Any],
    ],
    expected_preset_mode: str,
) -> None:
    """Test the breeze preset mode is exposed and reflects device state."""
    await init_integration(hass, aioclient_mock, mock_type=mock_type)

    state = hass.states.get("fan.modernformsfan_fan")
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] & FanEntityFeature.PRESET_MODE
    assert state.attributes.get(ATTR_PRESET_MODE) == expected_preset_mode


async def test_set_breeze_preset_mode(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting the breeze preset mode."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PRESET_MODE: PRESET_MODE_BREEZE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(wind=True)

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PRESET_MODE: PRESET_MODE_NORMAL,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(wind=False)


async def test_turn_on_with_breeze_preset_mode(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test turning on the fan with a breeze preset mode."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PRESET_MODE: PRESET_MODE_BREEZE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(on=True, wind=True)


async def test_turn_on_with_percentage_and_preset_mode(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test turning on the fan with both a percentage and a preset mode."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "fan.modernformsfan_fan",
                ATTR_PERCENTAGE: 100,
                ATTR_PRESET_MODE: PRESET_MODE_BREEZE,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(on=True, speed=6, wind=True)


async def test_turn_off_does_not_touch_wind(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test turning off the fan does not send the wind flag."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            FAN_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(on=False)


async def test_fan_sleep_timer_not_supported_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting a sleep timer on a Gen4 fan raises an error."""
    await init_integration_gen4(hass, aioclient_mock)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_FAN_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan", ATTR_SLEEP_TIME: 1},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "sleep_timer_not_supported"


async def test_clear_fan_sleep_timer_not_supported_gen4(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test clearing a sleep timer on a Gen4 fan raises an error."""
    await init_integration_gen4(hass, aioclient_mock)

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CLEAR_FAN_SLEEP_TIMER,
            {ATTR_ENTITY_ID: "fan.modernformsfan_fan"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "sleep_timer_not_supported"
