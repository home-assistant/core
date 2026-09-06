"""Tests for the Modern Forms number platform."""

from unittest.mock import patch

from aiomodernforms import ModernFormsConnectionError
import pytest

from homeassistant.components.modern_forms.const import DOMAIN
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import (
    init_integration,
    modern_forms_breeze_active_call_mock,
    modern_forms_breeze_call_mock,
)

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


async def test_breeze_intensity_state_active(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test the breeze intensity number reads wind_speed from an active breeze."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_active_call_mock
    )

    state = hass.states.get("number.modernformsfan_breeze_intensity")
    assert state
    assert state.state == "3"


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


async def test_set_breeze_intensity_connection_error(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test error handling of the breeze intensity number."""
    await init_integration(
        hass, aioclient_mock, mock_type=modern_forms_breeze_call_mock
    )

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
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.modernformsfan_breeze_intensity",
                ATTR_VALUE: 3,
            },
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "communication_error"

    state = hass.states.get("number.modernformsfan_breeze_intensity")
    assert state.state == STATE_UNAVAILABLE
