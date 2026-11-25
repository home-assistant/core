"""Tests for energy LLM tools."""

import json
from typing import Any

import probatio
import pytest
from pytest_homeassistant.common import MockUser

from homeassistant.components.energy import DOMAIN, data
from homeassistant.components.energy.data import async_get_manager
from homeassistant.components.energy.llm import async_get_tools
from homeassistant.components.recorder import Recorder
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

GET_TOOL = "energy__get_preferences"
UPDATE_TOOL = "energy__update_preferences"

GRID_SOURCE = {
    "stat_energy_from": "sensor.grid_import",
    "stat_energy_to": None,
    "stat_cost": None,
    "entity_energy_price": None,
    "number_energy_price": None,
    "stat_compensation": None,
    "entity_energy_price_export": None,
    "number_energy_price_export": None,
}
SOLAR_SOURCE = {
    "stat_energy_from": "sensor.solar",
    "config_entry_solar_forecast": None,
}
BATTERY_SOURCE = {
    "stat_energy_from": "sensor.battery_out",
    "stat_energy_to": "sensor.battery_in",
    "power_config": {"stat_rate_inverted": "sensor.battery_power"},
}
EMPTY_PREFERENCES = {
    "grid_sources": [],
    "solar_sources": [],
    "battery_sources": [],
    "gas_sources": [],
    "water_sources": [],
    "home_sources": [],
    "device_consumption": [],
    "device_consumption_water": [],
    "device_consumption_gas": [],
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


def _objects_without_properties(schema: Any, path: str = "") -> list[str]:
    """Return the paths of objects in an OpenAPI schema that list no properties."""
    if isinstance(schema, list):
        return [
            missing
            for index, item in enumerate(schema)
            for missing in _objects_without_properties(item, f"{path}[{index}]")
        ]
    if not isinstance(schema, dict):
        return []
    missing = (
        [path]
        if schema.get("type") == "object" and not schema.get("properties")
        else []
    )
    for key, value in schema.items():
        missing.extend(_objects_without_properties(value, f"{path}.{key}"))
    return missing


async def test_update_parameters_list_all_properties(api: llm.APIInstance) -> None:
    """Test every object in the update parameters lists its properties.

    Some LLM providers, like Gemini, cannot fill in an object without properties.
    """
    tool = next(tool for tool in api.tools if tool.name == UPDATE_TOOL)
    schema = probatio.to_openapi(
        tool.parameters, custom_serializer=api.custom_serializer
    )
    assert _objects_without_properties(schema) == []


def _fields(schema: Any) -> set[str]:
    """Return the field names of a schema, without the type and removed fields."""
    if isinstance(schema, probatio.All):
        schema = schema.validators[0]
    if isinstance(schema, probatio.Schema):
        schema = schema.schema
    return {
        str(key)
        for key in schema
        if str(key) != "type" and not isinstance(key, probatio.Remove)
    }


@pytest.mark.parametrize(
    ("key", "schema", "power_config_schema"),
    [
        ("grid_sources", data.GRID_SOURCE_SCHEMA, data.POWER_CONFIG_SCHEMA),
        ("solar_sources", data.SOLAR_SOURCE_SCHEMA, None),
        (
            "battery_sources",
            data.BATTERY_SOURCE_SCHEMA,
            data.BATTERY_POWER_CONFIG_SCHEMA,
        ),
        ("gas_sources", data.GAS_SOURCE_SCHEMA, None),
        ("water_sources", data.WATER_SOURCE_SCHEMA, None),
        ("home_sources", data.HOME_SOURCE_SCHEMA, None),
    ],
)
async def test_update_parameters_declare_all_fields(
    api: llm.APIInstance,
    key: str,
    schema: probatio.All | probatio.Schema,
    power_config_schema: probatio.All | None,
) -> None:
    """Test the update parameters declare every field of the energy schemas.

    An update replaces a whole list, so a field missing here is lost.
    """
    tool = next(tool for tool in api.tools if tool.name == UPDATE_TOOL)
    item = tool.parameters.schema[key][0]
    assert _fields(item) == _fields(schema)
    if power_config_schema is not None:
        assert _fields(item["power_config"]) == _fields(power_config_schema)


async def test_get_preferences_not_configured(api: llm.APIInstance) -> None:
    """Test getting the preferences before energy is configured."""
    result = await api.async_call_tool(llm.ToolInput(GET_TOOL, {}))

    assert result == llm.ToolResult(data=EMPTY_PREFERENCES)


async def test_get_preferences(hass: HomeAssistant, api: llm.APIInstance) -> None:
    """Test getting the energy sources per type."""
    manager = await async_get_manager(hass)
    await manager.async_update(
        {
            "energy_sources": [
                {"type": "solar", **SOLAR_SOURCE},
                {"type": "grid", **GRID_SOURCE},
            ],
            "device_consumption": [{"stat_consumption": "sensor.fridge"}],
        }
    )

    result = await api.async_call_tool(llm.ToolInput(GET_TOOL, {}))

    assert result == llm.ToolResult(
        data={
            **EMPTY_PREFERENCES,
            "grid_sources": [GRID_SOURCE],
            "solar_sources": [SOLAR_SOURCE],
            "device_consumption": [{"stat_consumption": "sensor.fridge"}],
        }
    )


async def test_update_preferences(hass: HomeAssistant, api: llm.APIInstance) -> None:
    """Test that an update replaces only the given lists."""
    manager = await async_get_manager(hass)
    await manager.async_update(
        {
            "energy_sources": [
                {"type": "grid", **GRID_SOURCE},
                {"type": "battery", **BATTERY_SOURCE},
            ]
        }
    )

    result = await api.async_call_tool(
        llm.ToolInput(
            UPDATE_TOOL,
            {
                "solar_sources": [{"stat_energy_from": "sensor.solar"}],
                "device_consumption_water": [{"stat_consumption": "sensor.shower"}],
            },
        )
    )

    assert not result.error
    assert result.data["preferences"] == {
        **EMPTY_PREFERENCES,
        "grid_sources": [GRID_SOURCE],
        "solar_sources": [{"stat_energy_from": "sensor.solar"}],
        # A power_config generates the stat_rate
        "battery_sources": [
            {**BATTERY_SOURCE, "stat_rate": "sensor.battery_power_inverted"}
        ],
        "device_consumption_water": [{"stat_consumption": "sensor.shower"}],
    }
    assert [source["type"] for source in manager.data["energy_sources"]] == [
        "grid",
        "solar",
        "battery",
    ]
    # The sensors do not exist, so validation reports issues for each item
    validation = result.data["validation"]
    assert {key: len(value) for key, value in validation.items()} == {
        **dict.fromkeys(EMPTY_PREFERENCES, 0),
        "grid_sources": 1,
        "solar_sources": 1,
        "battery_sources": 1,
        "device_consumption_water": 1,
    }
    assert validation["solar_sources"][0] == [
        {
            "type": "statistics_not_defined",
            "affected_entities": [["sensor.solar", None]],
            "translation_placeholders": None,
        },
        {
            "type": "entity_not_defined",
            "affected_entities": [["sensor.solar", None]],
            "translation_placeholders": None,
        },
    ]
    assert validation["device_consumption_water"] == [
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
    ]
    # The MCP server encodes the result with the standard JSON encoder
    json.dumps(result.data)


async def test_update_preferences_round_trip(
    hass: HomeAssistant, api: llm.APIInstance
) -> None:
    """Test that the preferences from the get tool can be sent back unchanged."""
    manager = await async_get_manager(hass)
    await manager.async_update(
        {
            "energy_sources": [
                {"type": "grid", **GRID_SOURCE},
                {"type": "solar", **SOLAR_SOURCE},
                {"type": "battery", **BATTERY_SOURCE},
            ]
        }
    )
    stored = manager.data

    preferences = (await api.async_call_tool(llm.ToolInput(GET_TOOL, {}))).data
    result = await api.async_call_tool(llm.ToolInput(UPDATE_TOOL, preferences))

    assert not result.error
    assert manager.data == stored


async def test_update_preferences_invalid(
    hass: HomeAssistant, api: llm.APIInstance
) -> None:
    """Test that invalid preferences return an error and change nothing."""
    manager = await async_get_manager(hass)
    await manager.async_update({"energy_sources": [{"type": "grid", **GRID_SOURCE}]})
    stored = manager.data

    result = await api.async_call_tool(
        llm.ToolInput(
            UPDATE_TOOL,
            {"home_sources": [{"stat_energy_to": "a"}, {"stat_energy_to": "b"}]},
        )
    )

    assert result == llm.ToolResult(
        data={"error": "Only one home source is allowed"},
        error=True,
    )
    assert manager.data == stored


@pytest.mark.parametrize(
    "tool_args",
    [
        {"wind_sources": [{"stat_energy_from": "sensor.wind"}]},
        {"device_consumption": [{"name": "Fridge"}]},
        {"device_consumption_gas": "sensor.gas"},
        {"solar_sources": [{"stat_energy_from": "sensor.solar", "type": "grid"}]},
    ],
)
async def test_update_preferences_invalid_args(
    api: llm.APIInstance, tool_args: dict[str, Any]
) -> None:
    """Test that invalid arguments are rejected."""
    with pytest.raises(probatio.Invalid):
        await api.async_call_tool(llm.ToolInput(UPDATE_TOOL, tool_args))
