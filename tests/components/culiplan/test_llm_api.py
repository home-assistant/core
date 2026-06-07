"""Tests for the LLM API."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.culiplan import CuliplanRuntimeData
from homeassistant.components.culiplan.api import CuliplanApiError
from homeassistant.components.culiplan.const import DOMAIN
from homeassistant.components.culiplan.llm_api import (
    LLM_API_ID,
    CuliplanLLMAPI,
    _filter_expiring,
    _get_client,
    _not_configured,
    _slot_in_range,
    async_register_llm_api,
    async_unregister_llm_api,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from tests.common import MockConfigEntry


def _ctx(hass: HomeAssistant) -> llm.LLMContext:
    """Return a minimal LLM context for tool calls."""
    return llm.LLMContext(
        platform="test",
        context=None,
        language="en",
        assistant=None,
        device_id=None,
    )


def _tool_input(tool: str, args: dict[str, object]) -> llm.ToolInput:
    """Return a tool input."""
    return llm.ToolInput(tool_name=tool, tool_args=args)


async def test_register_and_unregister(hass: HomeAssistant) -> None:
    """Registering and unregistering the API is refcounted across entries."""
    async_register_llm_api(hass)
    apis = hass.data.get("llm", {})
    assert LLM_API_ID in apis
    # Second register from a second entry holds the API alive past one unload.
    async_register_llm_api(hass)
    assert LLM_API_ID in apis
    async_unregister_llm_api(hass)
    assert LLM_API_ID in apis, "API must survive while another entry holds it"
    # Last unregister drops it.
    async_unregister_llm_api(hass)
    assert LLM_API_ID not in apis
    # Extra unregister is a no-op.
    async_unregister_llm_api(hass)


async def test_unregister_when_never_registered(hass: HomeAssistant) -> None:
    """Unregister is a no-op when the API was never registered."""
    async_unregister_llm_api(hass)


async def test_get_client_returns_none_without_entry(hass: HomeAssistant) -> None:
    """Without a config entry, ``_get_client`` returns None."""
    assert _get_client(hass) is None


async def test_get_client_returns_first_entry(hass: HomeAssistant) -> None:
    """With a configured entry, ``_get_client`` returns its API client."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())
    assert _get_client(hass) is client


def test_not_configured_shape() -> None:
    """``_not_configured`` returns the expected error envelope."""
    res = _not_configured()
    assert res["error"] == "not_configured"


def test_slot_in_range() -> None:
    """The date filter handles all edge cases."""
    assert _slot_in_range("2099-01-15", None, None)
    assert _slot_in_range("2099-01-15", "2099-01-15", "2099-01-16")
    assert not _slot_in_range("2099-01-14", "2099-01-15", None)
    assert not _slot_in_range("2099-01-17", None, "2099-01-16")
    assert _slot_in_range(12345, None, None)  # non-string passthrough


def test_filter_expiring_drops_bad_data() -> None:
    """Invalid expiry strings, non-dict items, and expired-too-late are dropped."""

    soon = (datetime.now(tz=UTC) + timedelta(days=1)).isoformat()
    later = (datetime.now(tz=UTC) + timedelta(days=365)).isoformat()
    items = [
        {"id": "p1", "expiresAt": soon},
        {"id": "p2", "expiresAt": "not-a-date"},
        {"id": "p3"},  # no expiry
        "not-a-dict",
        {"id": "p4", "expiresAt": later},  # way after cutoff
    ]
    res = _filter_expiring(items, within_days=7)
    assert len(res) == 1
    assert res[0]["id"] == "p1"


async def test_get_meal_plan_not_configured(hass: HomeAssistant) -> None:
    """Tool returns the not-configured envelope when no entry exists."""
    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_meal_plan")
    result = await tool.async_call(hass, _tool_input("get_meal_plan", {}), _ctx(hass))
    assert result["error"] == "not_configured"


async def test_get_meal_plan_happy_path(hass: HomeAssistant) -> None:
    """Tool returns plans filtered by date when range is supplied."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_meal_plans = AsyncMock(
        return_value=[
            {
                "id": "current",
                "slots": [
                    {"date": "2099-01-15T18:00:00Z"},
                    {"date": "2099-02-15T18:00:00Z"},
                ],
            }
        ]
    )
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_meal_plan")
    result = await tool.async_call(
        hass,
        _tool_input(
            "get_meal_plan",
            {"start_date": "2099-01-01", "end_date": "2099-01-31"},
        ),
        _ctx(hass),
    )
    assert result["count"] == 1


async def test_get_meal_plan_api_error(hass: HomeAssistant) -> None:
    """A backend error bubbles up as an ``api_error`` envelope."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_meal_plans = AsyncMock(side_effect=CuliplanApiError("boom"))
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_meal_plan")
    result = await tool.async_call(hass, _tool_input("get_meal_plan", {}), _ctx(hass))
    assert result["error"] == "api_error"


async def test_add_to_shopping_list_tool(hass: HomeAssistant) -> None:
    """The add-to-shopping-list tool delegates to the API client."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_add_shopping_item = AsyncMock(return_value={"id": "x"})
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "add_to_shopping_list")
    result = await tool.async_call(
        hass,
        _tool_input("add_to_shopping_list", {"name": "Milk", "quantity": "1L"}),
        _ctx(hass),
    )
    assert result["added"] is True
    assert result["item_id"] == "x"


async def test_add_to_shopping_list_tool_api_error(hass: HomeAssistant) -> None:
    """The tool returns ``api_error`` on backend failure."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_add_shopping_item = AsyncMock(side_effect=CuliplanApiError("x"))
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "add_to_shopping_list")
    result = await tool.async_call(
        hass,
        _tool_input("add_to_shopping_list", {"name": "Milk"}),
        _ctx(hass),
    )
    assert result["error"] == "api_error"


async def test_get_pantry_items_tool(hass: HomeAssistant) -> None:
    """Pantry tool slims, filters, and reports truncation."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()

    far = (datetime.now(tz=UTC) + timedelta(days=10)).isoformat()
    client.async_get_pantry_items = AsyncMock(
        return_value=[{"id": f"p{i}", "name": "X", "expiresAt": far} for i in range(60)]
    )
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_pantry_items")
    result = await tool.async_call(
        hass,
        _tool_input("get_pantry_items", {"expiring_within_days": 30}),
        _ctx(hass),
    )
    assert result["count"] == 50
    assert result["truncated"] is True


async def test_get_pantry_items_api_error(hass: HomeAssistant) -> None:
    """Pantry tool returns ``api_error`` on backend failure."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    client.async_get_pantry_items = AsyncMock(side_effect=CuliplanApiError("x"))
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())

    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_pantry_items")
    result = await tool.async_call(
        hass, _tool_input("get_pantry_items", {}), _ctx(hass)
    )
    assert result["error"] == "api_error"


async def test_find_recipes_tool(hass: HomeAssistant) -> None:
    """Recipe search normalises both envelope shapes."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())
    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "find_recipes_by_ingredients")

    # Envelope shape.
    client.async_get = AsyncMock(
        return_value={
            "data": [
                {"id": "r1", "title": "Soup", "prepTime": 20, "servings": 4},
            ]
        }
    )
    result = await tool.async_call(
        hass,
        _tool_input("find_recipes_by_ingredients", {"ingredients": ["onion"]}),
        _ctx(hass),
    )
    assert result["count"] == 1
    assert result["recipes"][0]["title"] == "Soup"

    # Bare-list shape.
    client.async_get = AsyncMock(
        return_value=[
            {"id": "r2", "title": "Pasta", "prepTimeMinutes": 30, "servings": 2},
        ]
    )
    result = await tool.async_call(
        hass,
        _tool_input(
            "find_recipes_by_ingredients", {"ingredients": ["pasta", "tomato"]}
        ),
        _ctx(hass),
    )
    assert result["recipes"][0]["prep_time_minutes"] == 30

    # Unexpected shape → empty.
    client.async_get = AsyncMock(return_value="oops")
    result = await tool.async_call(
        hass,
        _tool_input("find_recipes_by_ingredients", {"ingredients": ["x"]}),
        _ctx(hass),
    )
    assert result["recipes"] == []

    # API error.
    client.async_get = AsyncMock(side_effect=CuliplanApiError("x"))
    result = await tool.async_call(
        hass,
        _tool_input("find_recipes_by_ingredients", {"ingredients": ["x"]}),
        _ctx(hass),
    )
    assert result["error"] == "api_error"


async def test_get_recipe_tool(hass: HomeAssistant) -> None:
    """The get-recipe tool trims, handles missing recipes, and api errors."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u")
    entry.add_to_hass(hass)
    client = MagicMock()
    entry.runtime_data = CuliplanRuntimeData(client=client, coordinator=MagicMock())
    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    tool = next(t for t in api_inst.tools if t.name == "get_recipe")

    client.async_get = AsyncMock(
        return_value={"id": "r1", "title": "X", "secretField": "drop"}
    )
    result = await tool.async_call(
        hass, _tool_input("get_recipe", {"recipe_id": "r1"}), _ctx(hass)
    )
    assert result["recipe"]["title"] == "X"
    assert "secretField" not in result["recipe"]

    client.async_get = AsyncMock(return_value="oops")
    result = await tool.async_call(
        hass, _tool_input("get_recipe", {"recipe_id": "r1"}), _ctx(hass)
    )
    assert result["error"] == "not_found"

    client.async_get = AsyncMock(side_effect=CuliplanApiError("x"))
    result = await tool.async_call(
        hass, _tool_input("get_recipe", {"recipe_id": "r1"}), _ctx(hass)
    )
    assert result["error"] == "api_error"


async def test_tools_not_configured_paths(hass: HomeAssistant) -> None:
    """Each tool returns the not-configured envelope when no entry exists."""
    inst = CuliplanLLMAPI(hass)
    api_inst = await inst.async_get_api_instance(_ctx(hass))
    for tool in api_inst.tools:
        args: dict[str, object] = {}
        if tool.name == "add_to_shopping_list":
            args = {"name": "Milk"}
        elif tool.name == "find_recipes_by_ingredients":
            args = {"ingredients": ["x"]}
        elif tool.name == "get_recipe":
            args = {"recipe_id": "r1"}
        result = await tool.async_call(hass, _tool_input(tool.name, args), _ctx(hass))
        assert result["error"] == "not_configured"
