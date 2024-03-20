"""Tests for the humidifier intents."""

import pytest

from homeassistant.components.humidifier import (
    ATTR_AVAILABLE_MODES,
    ATTR_HUMIDITY,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    intent,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.intent import IntentHandleError, async_handle

from tests.common import async_mock_service


async def test_intent_set_humidity(hass: HomeAssistant) -> None:
    """Test the set humidity intent."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier", STATE_ON, {ATTR_HUMIDITY: 40}
    )
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    result = await async_handle(
        hass,
        "test",
        intent.INTENT_HUMIDITY,
        {"name": {"value": "Bedroom humidifier"}, "humidity": {"value": "50"}},
    )
    await hass.async_block_till_done()

    assert result.speech["plain"]["speech"] == "The bedroom humidifier is set to 50%"

    assert len(turn_on_calls) == 0
    assert len(humidity_calls) == 1
    call = humidity_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_HUMIDITY
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert call.data.get(ATTR_HUMIDITY) == 50


async def test_intent_set_humidity_and_turn_on(hass: HomeAssistant) -> None:
    """Test the set humidity intent for turned off humidifier."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier", STATE_OFF, {ATTR_HUMIDITY: 40}
    )
    humidity_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    result = await async_handle(
        hass,
        "test",
        intent.INTENT_HUMIDITY,
        {"name": {"value": "Bedroom humidifier"}, "humidity": {"value": "50"}},
    )
    await hass.async_block_till_done()

    assert (
        result.speech["plain"]["speech"]
        == "Turned bedroom humidifier on and set humidity to 50%"
    )

    assert len(turn_on_calls) == 1
    call = turn_on_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert len(humidity_calls) == 1
    call = humidity_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_HUMIDITY
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert call.data.get(ATTR_HUMIDITY) == 50


async def test_intent_set_mode(hass: HomeAssistant) -> None:
    """Test the set mode intent."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier",
        STATE_ON,
        {
            ATTR_HUMIDITY: 40,
            ATTR_SUPPORTED_FEATURES: 1,
            ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_MODE: "home",
        },
    )
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    result = await async_handle(
        hass,
        "test",
        intent.INTENT_MODE,
        {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "away"}},
    )
    await hass.async_block_till_done()

    assert (
        result.speech["plain"]["speech"]
        == "The mode for bedroom humidifier is set to away"
    )

    assert len(turn_on_calls) == 0
    assert len(mode_calls) == 1
    call = mode_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_MODE
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert call.data.get(ATTR_MODE) == "away"


async def test_intent_set_mode_and_turn_on(hass: HomeAssistant) -> None:
    """Test the set mode intent."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier",
        STATE_OFF,
        {
            ATTR_HUMIDITY: 40,
            ATTR_SUPPORTED_FEATURES: 1,
            ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_MODE: "home",
        },
    )
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    turn_on_calls = async_mock_service(hass, DOMAIN, SERVICE_TURN_ON)
    await intent.async_setup_intents(hass)

    result = await async_handle(
        hass,
        "test",
        intent.INTENT_MODE,
        {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "away"}},
    )
    await hass.async_block_till_done()

    assert (
        result.speech["plain"]["speech"]
        == "Turned bedroom humidifier on and set away mode"
    )

    assert len(turn_on_calls) == 1
    call = turn_on_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_TURN_ON
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert len(mode_calls) == 1
    call = mode_calls[0]
    assert call.domain == DOMAIN
    assert call.service == SERVICE_SET_MODE
    assert call.data.get(ATTR_ENTITY_ID) == "humidifier.bedroom_humidifier"
    assert call.data.get(ATTR_MODE) == "away"


async def test_intent_set_mode_tests_feature(hass: HomeAssistant) -> None:
    """Test the set mode intent where modes are not supported."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier", STATE_ON, {ATTR_HUMIDITY: 40}
    )
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    await intent.async_setup_intents(hass)

    with pytest.raises(IntentHandleError) as excinfo:
        await async_handle(
            hass,
            "test",
            intent.INTENT_MODE,
            {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "away"}},
        )
    assert str(excinfo.value) == "Entity bedroom humidifier does not support modes"
    assert len(mode_calls) == 0


@pytest.mark.parametrize("available_modes", [["home", "away"], None])
async def test_intent_set_unknown_mode(
    hass: HomeAssistant, available_modes: list[str] | None
) -> None:
    """Test the set mode intent for unsupported mode."""
    hass.states.async_set(
        "humidifier.bedroom_humidifier",
        STATE_ON,
        {
            ATTR_HUMIDITY: 40,
            ATTR_SUPPORTED_FEATURES: 1,
            ATTR_AVAILABLE_MODES: available_modes,
            ATTR_MODE: None,
        },
    )
    mode_calls = async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    await intent.async_setup_intents(hass)

    with pytest.raises(IntentHandleError) as excinfo:
        await async_handle(
            hass,
            "test",
            intent.INTENT_MODE,
            {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "eco"}},
        )
    assert str(excinfo.value) == "Entity bedroom humidifier does not support eco mode"
    assert len(mode_calls) == 0
