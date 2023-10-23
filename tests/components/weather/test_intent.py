"""Test weather intents."""


from homeassistant.components.weather import (
    DOMAIN,
    WeatherEntity,
    intent as weather_intent,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component


class MockWeatherEntity1(WeatherEntity):
    """Mock a Weather Entity."""

    name = "Weather 1"
    entity_id = "weather.test_1"


class MockWeatherEntity2(WeatherEntity):
    """Mock a Weather Entity."""

    name = "Weather 2"
    entity_id = "weather.test_2"


async def test_get_weather(hass: HomeAssistant) -> None:
    """Test get weather for first entity."""
    assert await async_setup_component(
        hass, "weather", {"weather": {"platform": "test"}}
    )

    entity1 = MockWeatherEntity1()
    entity2 = MockWeatherEntity2()

    await hass.data[DOMAIN].async_add_entities([entity1, entity2])

    await weather_intent.async_setup_intents(hass)

    # First entity will be chosen
    response = await intent.async_handle(hass, "test", "HassGetWeather", {})
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    state = response.matched_states[0]
    assert state.entity_id == entity1.entity_id

    # Named entity will be chosen
    response = await intent.async_handle(
        hass, "test", "HassGetWeather", {"name": {"value": "Weather 2"}}
    )
    assert response.response_type == intent.IntentResponseType.QUERY_ANSWER
    assert len(response.matched_states) == 1
    state = response.matched_states[0]
    assert state.entity_id == entity2.entity_id
