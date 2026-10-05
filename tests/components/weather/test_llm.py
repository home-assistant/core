"""Tests for the weather LLM tools platform."""

from datetime import timedelta

import pytest

from homeassistant.components import llm
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.components.weather import (
    DOMAIN,
    Forecast,
    WeatherEntityFeature,
    llm as weather_llm,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm as llm_helper
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import MockWeatherTest, create_entity

ENTITY_ID = "weather.testing"


@pytest.fixture(autouse=True)
async def setup_integrations(hass: HomeAssistant, config_flow_fixture: None) -> None:
    """Set up Home Assistant, weather, and LLM integrations."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})


def _llm_context() -> llm_helper.LLMContext:
    """Return an LLM context for the conversation assistant."""
    return llm_helper.LLMContext(
        platform="test_platform",
        context=Context(),
        language="*",
        assistant="conversation",
        device_id=None,
    )


async def _create_weather_entity(
    hass: HomeAssistant, supported_features: WeatherEntityFeature
) -> MockWeatherTest:
    """Create an exposed weather entity with the requested forecast support."""

    class MockWeatherForecast(MockWeatherTest):
        """Mock weather entity with a forecast."""

        async def async_forecast_daily(self) -> list[Forecast] | None:
            """Return a daily forecast."""
            return self.forecast_list

        async def async_forecast_hourly(self) -> list[Forecast] | None:
            """Return an hourly forecast."""
            return self.forecast_list

        async def async_forecast_twice_daily(self) -> list[Forecast] | None:
            """Return a twice-daily forecast."""
            return self.forecast_list

    entity = await create_entity(
        hass,
        MockWeatherForecast,
        None,
        supported_features=supported_features,
    )
    assert isinstance(entity, MockWeatherForecast)
    async_expose_entity(hass, "conversation", entity.entity_id, True)
    today = dt_util.start_of_local_day()
    entity.forecast_list = [{"datetime": today.isoformat(), "condition": "sunny"}]
    return entity


def _tool_args(forecast_type: str = "daily", period: str = "today") -> dict[str, str]:
    """Return valid forecast tool arguments."""
    return {"weather": "Testing", "forecast_type": forecast_type, "period": period}


async def test_get_forecast_tool(hass: HomeAssistant) -> None:
    """Test the exposed weather forecast tool returns forecast data."""
    await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    context = _llm_context()

    result = await llm.async_get_tools(hass, context, "assist")
    tools = {tool.name: tool for tool in result.tools}
    assert "weather__get_forecast" in tools

    tool = tools["weather__get_forecast"]
    assert tool.title == "Get weather forecast for a time window"
    assert tool.integration == DOMAIN
    assert tool.annotations == llm_helper.ToolAnnotations(
        read_only=True, destructive=False, idempotent=True, open_world=False
    )
    response = await tool.async_call(
        hass,
        llm_helper.ToolInput("weather__get_forecast", _tool_args()),
        context,
    )
    today = dt_util.start_of_local_day()
    assert response.data == {
        "forecast": [
            {
                "datetime": today.isoformat(),
                "condition": "sunny",
                "temperature": None,
            }
        ]
    }


async def test_get_forecast_tool_unsupported_forecast(hass: HomeAssistant) -> None:
    """Test the tool reports unsupported forecast types."""
    await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None
    tool = result.tools[0]

    with pytest.raises(
        HomeAssistantError,
        match="Weather entity does not support hourly forecasts",
    ):
        await tool.async_call(
            hass,
            llm_helper.ToolInput("weather__get_forecast", _tool_args("hourly")),
            _llm_context(),
        )


async def test_get_forecast_tool_ambiguous_target(hass: HomeAssistant) -> None:
    """Test the tool reports duplicate weather names instead of choosing one."""
    await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    hass.states.async_set(
        "weather.testing_two",
        "sunny",
        {"friendly_name": "Testing", "supported_features": 1},
    )
    async_expose_entity(hass, "conversation", "weather.testing_two", True)
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    with pytest.raises(HomeAssistantError, match="Weather entity name is ambiguous"):
        await result.tools[0].async_call(
            hass,
            llm_helper.ToolInput("weather__get_forecast", _tool_args()),
            _llm_context(),
        )


async def test_get_forecast_tool_no_forecast_data(hass: HomeAssistant) -> None:
    """Test the tool returns an empty forecast when data is unavailable."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    entity.forecast_list = None
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    response = await result.tools[0].async_call(
        hass,
        llm_helper.ToolInput("weather__get_forecast", _tool_args()),
        _llm_context(),
    )

    assert response.data == {"forecast": []}


async def test_get_forecast_tool_not_offered_without_exposed_forecast(
    hass: HomeAssistant,
) -> None:
    """Test the tool is hidden without an exposed forecast-capable entity."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    async_expose_entity(hass, "conversation", entity.entity_id, False)

    assert weather_llm.async_get_tools(hass, _llm_context(), "assist") is None
    assert weather_llm.async_get_tools(hass, _llm_context(), "other") is None


async def test_get_forecast_tool_not_found_after_unexposing(
    hass: HomeAssistant,
) -> None:
    """Test a previously exposed entity cannot be queried after it is hidden."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    async_expose_entity(hass, "conversation", entity.entity_id, False)
    with pytest.raises(HomeAssistantError, match="Weather entity not found"):
        await result.tools[0].async_call(
            hass,
            llm_helper.ToolInput("weather__get_forecast", _tool_args()),
            _llm_context(),
        )


async def test_get_forecast_tool_limits_requested_time_window(
    hass: HomeAssistant,
) -> None:
    """Test only forecast entries within the requested half-open interval are returned."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_HOURLY)
    today = dt_util.start_of_local_day()
    entity.forecast_list = [
        {"datetime": today.replace(hour=11).isoformat(), "condition": "cloudy"},
        {"datetime": today.replace(hour=12).isoformat(), "condition": "rainy"},
        {"datetime": today.replace(hour=14).isoformat(), "condition": "sunny"},
        {"datetime": today.replace(hour=18).isoformat(), "condition": "sunny"},
    ]
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    response = await result.tools[0].async_call(
        hass,
        llm_helper.ToolInput(
            "weather__get_forecast", _tool_args("hourly", "this_afternoon")
        ),
        _llm_context(),
    )

    assert response.data == {
        "forecast": [
            {
                "datetime": today.replace(hour=12).isoformat(),
                "condition": "rainy",
                "temperature": None,
            },
            {
                "datetime": today.replace(hour=14).isoformat(),
                "condition": "sunny",
                "temperature": None,
            },
        ]
    }


async def test_get_forecast_tool_maps_weekday_to_next_occurrence(
    hass: HomeAssistant,
) -> None:
    """Test a weekday period selects that weekday, including 'this Thursday'."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    today = dt_util.start_of_local_day()
    days_until_thursday = (3 - today.weekday()) % 7
    thursday = today + timedelta(days=days_until_thursday)
    entity.forecast_list = [
        {"datetime": (today - timedelta(days=1)).isoformat()},
        {"datetime": thursday.isoformat(), "condition": "rainy"},
        {
            "datetime": (thursday + timedelta(days=1)).isoformat(),
            "condition": "sunny",
        },
    ]
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    response = await result.tools[0].async_call(
        hass,
        llm_helper.ToolInput("weather__get_forecast", _tool_args("daily", "thursday")),
        _llm_context(),
    )
    assert response.data["forecast"][0]["condition"] == "rainy"


async def test_get_forecast_tool_maps_tomorrow(hass: HomeAssistant) -> None:
    """Test tomorrow selects the next local calendar day."""
    entity = await _create_weather_entity(hass, WeatherEntityFeature.FORECAST_DAILY)
    today = dt_util.start_of_local_day()
    tomorrow = today + timedelta(days=1)
    entity.forecast_list = [
        {"datetime": today.isoformat(), "condition": "cloudy"},
        {"datetime": tomorrow.isoformat(), "condition": "rainy"},
        {
            "datetime": (tomorrow + timedelta(days=1)).isoformat(),
            "condition": "sunny",
        },
    ]
    result = weather_llm.async_get_tools(hass, _llm_context(), "assist")
    assert result is not None

    response = await result.tools[0].async_call(
        hass,
        llm_helper.ToolInput("weather__get_forecast", _tool_args("daily", "tomorrow")),
        _llm_context(),
    )

    assert response.data["forecast"][0]["condition"] == "rainy"
