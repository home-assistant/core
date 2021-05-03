"""Tests for the Elgato Key Light light platform."""
from unittest.mock import patch

from elgato import ElgatoError

from homeassistant.components.elgato.const import DOMAIN, SERVICE_IDENTIFY
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
from homeassistant.helpers import entity_registry as er

from tests.common import mock_coro
from tests.components.elgato import init_integration
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_light_state(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the creation and values of the Elgato Key Lights."""
    await init_integration(hass, aioclient_mock)

    entity_registry = er.async_get(hass)

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
    ), patch(
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


async def test_light_identify(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test identifying an Elgato Light."""
    await init_integration(hass, aioclient_mock)

    with patch(
        "homeassistant.components.elgato.light.Elgato.identify",
        return_value=mock_coro(),
    ) as mock_identify:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IDENTIFY,
            {
                ATTR_ENTITY_ID: "light.frenck",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(mock_identify.mock_calls) == 1
        mock_identify.assert_called_with()


async def test_light_identify_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
) -> None:
    """Test error occurred during identifying an Elgato Light."""
    await init_integration(hass, aioclient_mock)

    with patch(
        "homeassistant.components.elgato.light.Elgato.identify",
        side_effect=ElgatoError,
    ) as mock_identify:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_IDENTIFY,
            {
                ATTR_ENTITY_ID: "light.frenck",
            },
            blocking=True,
        )
        await hass.async_block_till_done()
        assert len(mock_identify.mock_calls) == 1

    assert "An error occurred while identifying the Elgato Light" in caplog.text
