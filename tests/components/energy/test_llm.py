"""Tests for energy LLM tools."""

import json

import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.energy import DOMAIN
from homeassistant.components.energy.data import EnergyManager, async_get_manager
from homeassistant.components.energy.llm import async_get_tools
from homeassistant.components.recorder import Recorder
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

GET_TOOL = "energy__get_preferences"
UPDATE_TOOL = "energy__update_preferences"

GRID_SOURCE = {
    "type": "grid",
    "stat_energy_from": "sensor.grid_import",
    "stat_energy_to": None,
    "stat_cost": None,
    "entity_energy_price": None,
    "number_energy_price": None,
    "stat_compensation": None,
    "entity_energy_price_export": None,
    "number_energy_price_export": None,
}


@pytest.fixture
def llm_context() -> llm.LLMContext:
    """Return an LLM context."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="*",
        assistant="conversation",
        device_id=None,
    )


@pytest.fixture(autouse=True)
async def setup_integration(recorder_mock: Recorder, hass: HomeAssistant) -> None:
    """Set up the integration."""
    assert await async_setup_component(hass, DOMAIN, {})
    assert await async_setup_component(hass, "llm", {})


@pytest.fixture
async def api(
    hass: HomeAssistant, hass_admin_user: MockUser, llm_context: llm.LLMContext
) -> llm.APIInstance:
    """Return the Home Assistant API."""
    llm_context.context = Context(user_id=hass_admin_user.id)
    return await llm.async_get_api(hass, llm.LLM_API_HOME_ASSISTANT, llm_context)


async def test_async_get_tools(
    hass: HomeAssistant, llm_context: llm.LLMContext
) -> None:
    """Test async_get_tools returns tools only for the Home Assistant API."""
    assert async_get_tools(hass, llm_context, llm.LLM_API_ASSIST) is None

    tools = async_get_tools(hass, llm_context, llm.LLM_API_HOME_ASSISTANT)
    assert tools is not None
    assert [tool.name for tool in tools.tools] == [GET_TOOL, UPDATE_TOOL]
    assert all(tool.integration == DOMAIN for tool in tools.tools)


async def test_get_preferences_not_configured(api: llm.APIInstance) -> None:
    """Test getting the preferences before energy is configured."""
    result = await api.async_call_tool(llm.ToolInput(GET_TOOL, {}))

    assert result == llm.ToolResult(
        data={"result": EnergyManager.default_preferences()}
    )


async def test_get_preferences(hass: HomeAssistant, api: llm.APIInstance) -> None:
    """Test getting the configured preferences."""
    manager = await async_get_manager(hass)
    await manager.async_update({"energy_sources": [GRID_SOURCE]})

    result = await api.async_call_tool(llm.ToolInput(GET_TOOL, {}))

    assert result == llm.ToolResult(
        data={
            "result": {
                **EnergyManager.default_preferences(),
                "energy_sources": [GRID_SOURCE],
            }
        }
    )


async def test_update_preferences(hass: HomeAssistant, api: llm.APIInstance) -> None:
    """Test that an update replaces only the given lists."""
    manager = await async_get_manager(hass)
    await manager.async_update({"energy_sources": [GRID_SOURCE]})

    result = await api.async_call_tool(
        llm.ToolInput(
            UPDATE_TOOL,
            {"device_consumption_water": [{"stat_consumption": "sensor.shower"}]},
        )
    )

    expected = {
        **EnergyManager.default_preferences(),
        "energy_sources": [GRID_SOURCE],
        "device_consumption_water": [{"stat_consumption": "sensor.shower"}],
    }
    assert not result.error
    assert result.data["result"] == expected
    assert manager.data == expected
    # The sensors do not exist, so validation reports issues for each item
    assert result.data["validation"] == {
        "energy_sources": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": [["sensor.grid_import", None]],
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": [["sensor.grid_import", None]],
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption": [],
        "device_consumption_water": [
            [
                {
                    "type": "statistics_not_defined",
                    "affected_entities": [["sensor.shower", None]],
                    "translation_placeholders": None,
                },
                {
                    "type": "entity_not_defined",
                    "affected_entities": [["sensor.shower", None]],
                    "translation_placeholders": None,
                },
            ]
        ],
        "device_consumption_gas": [],
    }
    # The MCP server encodes the result with the standard JSON encoder
    json.dumps(result.data)


@pytest.mark.parametrize(
    "tool_args",
    [
        {"energy_sources": [{"type": "wind", "stat_energy_from": "sensor.wind"}]},
        {"device_consumption": [{"name": "Fridge"}]},
        {"device_consumption_gas": "sensor.gas"},
    ],
)
async def test_update_preferences_invalid(
    hass: HomeAssistant, api: llm.APIInstance, tool_args: dict
) -> None:
    """Test that invalid preferences return an error and change nothing."""
    manager = await async_get_manager(hass)
    await manager.async_update({"energy_sources": [GRID_SOURCE]})

    result = await api.async_call_tool(llm.ToolInput(UPDATE_TOOL, tool_args))

    assert result.error
    assert "error" in result.data
    assert manager.data == {
        **EnergyManager.default_preferences(),
        "energy_sources": [GRID_SOURCE],
    }
