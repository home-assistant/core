"""Tests for the Elgato Key Light light platform."""
from unittest.mock import patch

from homeassistant.components.elgato.light import ElgatoError
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant

from tests.common import mock_coro
from tests.components.elgato import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_light_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Elgato Key Lights."""
    await init_integration(hass, aioclient_mock)

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    # First segment of the strip
    state = hass.states.get("light.frenck")
    assert state
    assert state.attributes.get(ATTR_BRIGHTNESS) == 54
    assert state.attributes.get(ATTR_COLOR_TEMP) == 297
    assert state.state == STATE_ON

    entry = entity_registry.async_get("light.frenck")
    assert entry
    assert entry.unique_id == "CN11A1A00001"


async def test_light_change_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the change of state of a Elgato Key Light device."""
    await init_integration(hass, aioclient_mock)

    state = hass.states.get("light.frenck")
    assert state.state == STATE_ON

    with patch(
        "homeassistant.components.elgato.light.Elgato.light",
        return_value=mock_coro(),
    ) as mock_light:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {
                ATTR_ENTITY_ID: "light.frenck",
                ATTR_BRIGHTNESS: 255,
                ATTR_COLOR_TEMP: 100,
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(mock_light.mock_calls) == 1
        mock_light.assert_called_with(on=True, brightness=100, temperature=100)

    with patch(
        "homeassistant.components.elgato.light.Elgato.light",
        return_value=mock_coro(),
    ) as mock_light:
        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: "light.frenck"},
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(mock_light.mock_calls) == 1
        mock_light.assert_called_with(on=False)


async def test_light_unavailable(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test error/unavailable handling of an Elgato Key Light."""
    await init_integration(hass, aioclient_mock)
    with patch(
        "homeassistant.components.elgato.light.Elgato.light",
        side_effect=ElgatoError,
    ):
        with patch(
            "homeassistant.components.elgato.light.Elgato.state",
            side_effect=ElgatoError,
        ):
            await hass.services.async_call(
                LIGHT_DOMAIN,
                SERVICE_TURN_OFF,
                {ATTR_ENTITY_ID: "light.frenck"},
                blocking=True,
            )
            await hass.async_block_till_done()
            state = hass.states.get("light.frenck")
            assert state.state == STATE_UNAVAILABLE
