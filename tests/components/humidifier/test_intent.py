"""Tests for the humidifier intents."""

import pytest

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
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
from homeassistant.helpers.intent import (
    IntentHandleError,
    IntentResponseType,
    InvalidSlotInfo,
    MatchFailedError,
    MatchFailedReason,
    async_handle,
)
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


async def test_intent_set_humidity(hass: HomeAssistant) -> None:
    """Test the set humidity intent."""
    assert await async_setup_component(hass, "homeassistant", {})
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
        assistant=conversation.DOMAIN,
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
    assert await async_setup_component(hass, "homeassistant", {})
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
        assistant=conversation.DOMAIN,
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
    assert await async_setup_component(hass, "homeassistant", {})
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
        assistant=conversation.DOMAIN,
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
    assert await async_setup_component(hass, "homeassistant", {})
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
        assistant=conversation.DOMAIN,
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
    assert await async_setup_component(hass, "homeassistant", {})
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
            assistant=conversation.DOMAIN,
        )
    assert str(excinfo.value) == "Entity bedroom humidifier does not support modes"
    assert len(mode_calls) == 0


@pytest.mark.parametrize("available_modes", [["home", "away"], None])
async def test_intent_set_unknown_mode(
    hass: HomeAssistant, available_modes: list[str] | None
) -> None:
    """Test the set mode intent for unsupported mode."""
    assert await async_setup_component(hass, "homeassistant", {})
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
            assistant=conversation.DOMAIN,
        )
    assert str(excinfo.value) == "Entity bedroom humidifier does not support eco mode"
    assert len(mode_calls) == 0


async def test_intent_errors(hass: HomeAssistant) -> None:
    """Test the error conditions for set humidity and set mode intents."""
    assert await async_setup_component(hass, "homeassistant", {})
    entity_id = "humidifier.bedroom_humidifier"
    hass.states.async_set(
        entity_id,
        STATE_ON,
        {
            ATTR_HUMIDITY: 40,
            ATTR_SUPPORTED_FEATURES: 1,
            ATTR_AVAILABLE_MODES: ["home", "away"],
            ATTR_MODE: None,
        },
    )
    async_mock_service(hass, DOMAIN, SERVICE_SET_HUMIDITY)
    async_mock_service(hass, DOMAIN, SERVICE_SET_MODE)
    await intent.async_setup_intents(hass)

    # Humidifiers are exposed by default
    result = await async_handle(
        hass,
        "test",
        intent.INTENT_HUMIDITY,
        {"name": {"value": "Bedroom humidifier"}, "humidity": {"value": "50"}},
        assistant=conversation.DOMAIN,
    )
    assert result.response_type == IntentResponseType.ACTION_DONE

    result = await async_handle(
        hass,
        "test",
        intent.INTENT_MODE,
        {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "away"}},
        assistant=conversation.DOMAIN,
    )
    assert result.response_type == IntentResponseType.ACTION_DONE

    # Unexposing it should fail
    async_expose_entity(hass, conversation.DOMAIN, entity_id, False)

    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_HUMIDITY,
            {"name": {"value": "Bedroom humidifier"}, "humidity": {"value": "50"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == MatchFailedReason.ASSISTANT

    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_MODE,
            {"name": {"value": "Bedroom humidifier"}, "mode": {"value": "away"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == MatchFailedReason.ASSISTANT

    # Expose again to test other errors
    async_expose_entity(hass, conversation.DOMAIN, entity_id, True)

    # Empty name should fail
    with pytest.raises(InvalidSlotInfo):
        await async_handle(
            hass,
            "test",
            intent.INTENT_HUMIDITY,
            {"name": {"value": ""}, "humidity": {"value": "50"}},
            assistant=conversation.DOMAIN,
        )

    with pytest.raises(InvalidSlotInfo):
        await async_handle(
            hass,
            "test",
            intent.INTENT_MODE,
            {"name": {"value": ""}, "mode": {"value": "away"}},
            assistant=conversation.DOMAIN,
        )

    # Wrong name should fail
    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_HUMIDITY,
            {"name": {"value": "does not exist"}, "humidity": {"value": "50"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == MatchFailedReason.NAME

    with pytest.raises(MatchFailedError) as err:
        await async_handle(
            hass,
            "test",
            intent.INTENT_MODE,
            {"name": {"value": "does not exist"}, "mode": {"value": "away"}},
            assistant=conversation.DOMAIN,
        )
    assert err.value.result.no_match_reason == MatchFailedReason.NAME
