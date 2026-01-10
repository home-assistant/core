"""Test the SMN weather entity."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.smn_argentina.weather import format_condition
from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_SUNNY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    DOMAIN as WEATHER_DOMAIN,
    SERVICE_GET_FORECASTS,
)
from homeassistant.core import HomeAssistant

from . import init_integration


async def test_weather_entity_state(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather entity reports correct state."""
    # Patch is_up to ensure consistent day behavior
    with patch(
        "homeassistant.components.smn_argentina.weather.is_up", return_value=True
    ):
        await init_integration(hass)
        # Get weather entity - check all weather entities
        weather_entities = hass.states.async_entity_ids("weather")
        assert len(weather_entities) > 0, (
            f"No weather entities found. All entities: {hass.states.async_entity_ids()}"
        )

        state = hass.states.get(weather_entities[0])
        assert state is not None
        assert state.state == ATTR_CONDITION_SUNNY
        assert state.attributes["temperature"] == 22.5
        assert state.attributes["humidity"] == 65
        assert state.attributes["pressure"] == 1013.2
        assert state.attributes["wind_speed"] == 15.5
        assert state.attributes["wind_bearing"] == 180
        assert (
            state.attributes["attribution"]
            == "Data provided by Servicio Meteorológico Nacional de Argentina (SMN)"
        )


async def test_weather_daily_forecast(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather daily forecast service."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    entity_id = weather_entities[0]

    # Call forecast service
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"type": "daily", "entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert entity_id in response
    forecast = response[entity_id]["forecast"]
    assert isinstance(forecast, list)
    assert len(forecast) > 0

    # Check forecast structure
    first_day = forecast[0]
    assert ATTR_FORECAST_TIME in first_day
    assert ATTR_FORECAST_TEMP in first_day or ATTR_FORECAST_TEMP_LOW in first_day


async def test_weather_hourly_forecast(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather hourly forecast service."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    entity_id = weather_entities[0]

    # Call forecast service
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"type": "hourly", "entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    assert entity_id in response
    forecast = response[entity_id]["forecast"]
    assert isinstance(forecast, list)
    # Hourly forecast should have entries
    assert len(forecast) > 0


async def test_weather_condition_mapping(
    hass: HomeAssistant,
) -> None:
    """Test weather condition ID mapping."""
    # Test day conditions
    assert (
        format_condition({"id": 3, "description": "Despejado"}, sun_is_up=True)
        == ATTR_CONDITION_SUNNY
    )
    assert (
        format_condition({"id": 5, "description": "Despejado"}, sun_is_up=False)
        == ATTR_CONDITION_CLEAR_NIGHT
    )

    # Test sunny converted to clear-night at night
    assert (
        format_condition({"id": 3, "description": "Despejado"}, sun_is_up=False)
        == ATTR_CONDITION_CLEAR_NIGHT
    )

    # Test None handling
    assert format_condition(None, sun_is_up=True) == ATTR_CONDITION_SUNNY
    assert format_condition(None, sun_is_up=False) == ATTR_CONDITION_CLEAR_NIGHT

    # Test invalid dict
    assert format_condition({}, sun_is_up=True) == ATTR_CONDITION_SUNNY
    assert (
        format_condition({"description": "test"}, sun_is_up=True)
        == ATTR_CONDITION_SUNNY
    )


async def test_weather_entity_name(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather entity uses location name from API."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    state = hass.states.get(weather_entities[0])
    assert state is not None
    # The friendly name includes both device and entity name
    assert "Ciudad de Buenos Aires" in state.attributes["friendly_name"]


async def test_weather_entity_attributes(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather entity has all required attributes."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    state = hass.states.get(weather_entities[0])
    assert state is not None

    # Check all required attributes
    required_attrs = [
        "temperature",
        "humidity",
        "pressure",
        "wind_speed",
        "wind_bearing",
        "attribution",
        "friendly_name",
        "supported_features",
    ]

    for attr in required_attrs:
        assert attr in state.attributes, f"Missing attribute: {attr}"


async def test_weather_entity_optional_attributes(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather entity optional attributes."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    state = hass.states.get(weather_entities[0])
    assert state is not None

    # Check optional attributes that should be present
    assert "apparent_temperature" in state.attributes
    assert state.attributes["apparent_temperature"] == 21.0

    assert "visibility" in state.attributes
    assert state.attributes["visibility"] == 10000.0


async def test_weather_forecast_structure(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather forecast has correct structure."""
    await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    entity_id = weather_entities[0]

    # Call daily forecast service
    response = await hass.services.async_call(
        WEATHER_DOMAIN,
        SERVICE_GET_FORECASTS,
        {"type": "daily", "entity_id": entity_id},
        blocking=True,
        return_response=True,
    )

    assert response is not None
    forecast = response[entity_id]["forecast"]

    # Check first forecast entry structure
    if len(forecast) > 0:
        first_entry = forecast[0]
        # Should have either temperature or temp_low
        assert (
            ATTR_FORECAST_TEMP in first_entry or ATTR_FORECAST_TEMP_LOW in first_entry
        )
        # Should have time
        assert ATTR_FORECAST_TIME in first_entry


async def test_weather_update(
    hass: HomeAssistant,
    mock_smn_api_client,
    mock_token_manager,
) -> None:
    """Test weather entity updates when coordinator refreshes."""
    entry = await init_integration(hass)

    # Get weather entity
    weather_entities = hass.states.async_entity_ids("weather")
    assert len(weather_entities) > 0
    entity_id = weather_entities[0]

    # Get initial state
    state = hass.states.get(entity_id)
    assert state is not None
    initial_temp = state.attributes["temperature"]

    # Update mock data
    new_weather_data = {
        "temperature": 25.0,  # Different temperature
        "feels_like": 24.0,
        "humidity": 70,
        "pressure": 1015.0,
        "visibility": 10000,
        "weather": {"id": 3, "description": "Despejado"},
        "wind": {"speed": 20.0, "deg": 90},
        "location": {"id": "4864", "name": "Ciudad de Buenos Aires"},
    }
    mock_smn_api_client.async_get_current_weather = AsyncMock(
        return_value=new_weather_data
    )

    # Trigger coordinator refresh
    coordinator = entry.runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Get updated state
    state = hass.states.get(entity_id)
    assert state is not None
    # Temperature should be updated
    assert state.attributes["temperature"] == 25.0
    assert state.attributes["temperature"] != initial_temp
