"""Test weather intents."""
from unittest.mock import patch

import pytest

from homeassistant.components.weather import (
    DOMAIN,
    WeatherEntity,
    intent as weather_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


async def test_get_weather(hass: HomeAssistant) -> None:
    """Test get weather for first entity and by name."""
    assert await async_setup_component(hass, "weather", {"weather": {}})

    entity1 = WeatherEntity()
    entity1._attr_name = "Weather 1"
    entity1.entity_id = "weather.test_1"

    entity2 = WeatherEntity()
    entity2._attr_name = "Weather 2"
    entity2.entity_id = "weather.test_2"

    await hass.data[DOMAIN].async_add_entities([entity1, entity2])

    await weather_intent.async_setup_intents(hass)

    # First entity will be chosen
    response = await intent.async_handle(
        hass, "test", weather_intent.INTENT_GET_WEATHER, {}
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    state = response.matched_states[0]
    assert state.entity_id == entity1.entity_id

    # Named entity will be chosen
    response = await intent.async_handle(
        hass,
        "test",
        weather_intent.INTENT_GET_WEATHER,
        {"name": {"value": "Weather 2"}},
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    state = response.matched_states[0]
    assert state.entity_id == entity2.entity_id


async def test_get_weather_wrong_name(hass: HomeAssistant) -> None:
    """Test get weather with the wrong name."""
    assert await async_setup_component(hass, "weather", {"weather": {}})

    entity1 = WeatherEntity()
    entity1._attr_name = "Weather 1"
    entity1.entity_id = "weather.test_1"

    await hass.data[DOMAIN].async_add_entities([entity1])

    await weather_intent.async_setup_intents(hass)

    # Incorrect name
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(
            hass,
            "test",
            weather_intent.INTENT_GET_WEATHER,
            {"name": {"value": "not the right name"}},
        )


async def test_get_weather_no_entities(hass: HomeAssistant) -> None:
    """Test get weather with no weather entities."""
    assert await async_setup_component(hass, "weather", {"weather": {}})
    await weather_intent.async_setup_intents(hass)

    # No weather entities
    with pytest.raises(intent.IntentHandleError):
        await intent.async_handle(hass, "test", weather_intent.INTENT_GET_WEATHER, {})


async def test_get_weather_no_state(hass: HomeAssistant) -> None:
    """Test get weather when state is not returned."""
    assert await async_setup_component(hass, "weather", {"weather": {}})

    entity1 = WeatherEntity()
    entity1._attr_name = "Weather 1"
    entity1.entity_id = "weather.test_1"

    await hass.data[DOMAIN].async_add_entities([entity1])

    await weather_intent.async_setup_intents(hass)

    # Success with state
    response = await intent.async_handle(
        hass, "test", weather_intent.INTENT_GET_WEATHER, {}
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER

    # Failure without state
    with patch("homeassistant.core.StateMachine.get", return_value=None), pytest.raises(
        intent.IntentHandleError
    ):
        await intent.async_handle(hass, "test", weather_intent.INTENT_GET_WEATHER, {})
