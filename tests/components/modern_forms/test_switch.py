"""Tests for the Modern Forms switch platform."""

from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError
import pytest

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_switch_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and values of the Modern Forms switches."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("switch.modernformsfan_away_mode")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.modernformsfan_away_mode")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF_away_mode"

    state = hass.states.get("switch.modernformsfan_adaptive_learning")
    assert state
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.modernformsfan_adaptive_learning")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF_adaptive_learning"


async def test_switch_change_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the change of state of the Modern Forms switches."""
    await init_integration(hass, aioclient_mock)

    # Away Mode
    with patch("aiomodernforms.ModernFormsDevice.away") as away_mock:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.modernformsfan_away_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()
        away_mock.assert_called_once_with(away=True)

    with patch("aiomodernforms.ModernFormsDevice.away") as away_mock:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.modernformsfan_away_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()
        away_mock.assert_called_once_with(away=False)

    # Adaptive Learning
    with patch(
        "aiomodernforms.ModernFormsDevice.adaptive_learning"
    ) as adaptive_learning_mock:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.modernformsfan_adaptive_learning"},
            blocking=True,
        )
        await hass.async_block_till_done()
        adaptive_learning_mock.assert_called_once_with(adaptive_learning=True)

    with patch(
        "aiomodernforms.ModernFormsDevice.adaptive_learning"
    ) as adaptive_learning_mock:
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "switch.modernformsfan_adaptive_learning"},
            blocking=True,
        )
        await hass.async_block_till_done()
        adaptive_learning_mock.assert_called_once_with(adaptive_learning=False)


async def test_switch_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the Modern Forms switches."""
    await init_integration(hass, aioclient_mock)

    aioclient_mock.clear_requests()
    aioclient_mock.post("http://192.168.1.123:80/mf", text="", status=400)

    with patch(
        "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.modernformsfan_away_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.modernformsfan_away_mode")
        assert state.state == STATE_OFF
        assert "Invalid response from API" in caplog.text


async def test_switch_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error handling of the Modern Forms switches."""
    await init_integration(hass, aioclient_mock)

    with (
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.update"
        ),
        patch(
            "homeassistant.components.modern_forms.coordinator.ModernFormsDevice.away",
            side_effect=ModernFormsConnectionError,
        ),
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "switch.modernformsfan_away_mode"},
            blocking=True,
        )
        await hass.async_block_till_done()

        state = hass.states.get("switch.modernformsfan_away_mode")
        assert state.state == STATE_UNAVAILABLE
