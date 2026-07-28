"""Tests for the Modern Forms number platform."""

from unittest.mock import patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import init_integration, modern_forms_breeze_call_mock

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_no_breeze_intensity_without_wind_support(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the breeze intensity number isn't created for fans without wind support."""
    await init_integration(hass, aioclient_mock)

    assert hass.states.get("number.modernformsfan_breeze_intensity") is None


async def test_breeze_intensity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the creation and value of the breeze intensity number."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    state = hass.states.get("number.modernformsfan_breeze_intensity")
    assert state
    assert state.state == "2"

    entry = entity_registry.async_get("number.modernformsfan_breeze_intensity")
    assert entry
    assert entry.unique_id == "AA:BB:CC:DD:EE:FF_breeze_intensity"


async def test_set_breeze_intensity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test setting the breeze intensity."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

    with patch("aiomodernforms.ModernFormsDevice.fan") as fan_mock:
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.modernformsfan_breeze_intensity",
                ATTR_VALUE: 3,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        fan_mock.assert_called_once_with(wind_speed=3)
