"""Culiplan LLM API.

Exposes Culiplan tools to any Home Assistant Conversation Agent via
:func:`homeassistant.helpers.llm.async_register_api`. With this in place,
a user with the built-in HA Conversation Agent (OpenAI / Anthropic /
Google / Ollama / Voice Preview) can ask "what's for dinner?" or "add
milk to my shopping list" and the agent calls Culiplan natively.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
import logging
from typing import Any, cast
from urllib.parse import quote

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.util.json import JsonObjectType

from .api import CuliplanApiClient, CuliplanApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

LLM_API_ID = f"{DOMAIN}-llm"

# Refcount of config entries that hold the LLM API alive. The API is a
# process-wide singleton — register on first entry, unregister on last.
_LLM_REFCOUNT_KEY = f"{DOMAIN}_llm_refcount"
_LLM_UNREGISTER_KEY = f"{DOMAIN}_llm_unregister"

_PROMPT = (
    "You can answer questions about the user's meal plan, recipes, "
    "shopping list, and pantry. Use the Culiplan tools to fetch live "
    "data — never invent recipes or quantities. If a tool returns no "
    "results, say so honestly. Dates are ISO 8601 (YYYY-MM-DD)."
)


class CuliplanLLMAPI(llm.API):
    """Expose Culiplan tools to any HA Conversation Agent."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialise the API with a fixed id and display name."""
        super().__init__(hass=hass, id=LLM_API_ID, name="Culiplan")

    async def async_get_api_instance(
        self, llm_context: llm.LLMContext
    ) -> llm.APIInstance:
        """Return a per-call ``APIInstance`` carrying the Culiplan tools."""
        return llm.APIInstance(
            api=self,
            api_prompt=_PROMPT,
            llm_context=llm_context,
            tools=[
                _GetMealPlanTool(),
                _AddToShoppingListTool(),
                _GetPantryItemsTool(),
                _FindRecipesByIngredientsTool(),
                _GetRecipeTool(),
            ],
        )


def _get_client(hass: HomeAssistant) -> CuliplanApiClient | None:
    """Return the first configured Culiplan client or ``None``."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        runtime = getattr(entry, "runtime_data", None)
        if runtime is not None:
            return cast(CuliplanApiClient, runtime.client)
    return None


def _not_configured() -> JsonObjectType:
    """Return the canonical "integration not yet configured" tool response."""
    return {
        "error": "not_configured",
        "message": (
            "Culiplan is not configured. Ask the user to set it up "
            "under Settings → Devices & Services."
        ),
    }


class _GetMealPlanTool(llm.Tool):
    """Return the user's current meal plan."""

    name = "get_meal_plan"
    description = (
        "Return the user's current meal plan. Optionally filter to a "
        "date range with start_date / end_date (ISO 8601, YYYY-MM-DD)."
    )
    parameters = vol.Schema(
        {
            vol.Optional("start_date"): str,
            vol.Optional("end_date"): str,
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Fetch and optionally trim the meal plan."""
        client = _get_client(hass)
        if client is None:
            return _not_configured()
        try:
            plans = await client.async_get_meal_plans()
        except CuliplanApiError as err:
            return {"error": "api_error", "message": str(err)}

        start = tool_input.tool_args.get("start_date")
        end = tool_input.tool_args.get("end_date")
        if (start or end) and plans:
            plan = plans[0]
            slots = [
                s
                for s in plan.get("slots", [])
                if _slot_in_range(s.get("date"), start, end)
            ]
            plans = [{**plan, "slots": slots}]

        return cast(
            JsonObjectType,
            {
                "meal_plan": plans,
                "count": sum(len(p.get("slots", [])) for p in plans),
            },
        )


class _AddToShoppingListTool(llm.Tool):
    """Add an item to the user's shopping list."""

    name = "add_to_shopping_list"
    description = (
        "Add an item to the Culiplan shopping list. Use this for "
        "'add milk to my shopping list' or 'put two kilograms of "
        "potatoes on the list'."
    )
    parameters = vol.Schema(
        {
            vol.Required("name"): vol.All(str, vol.Length(min=1, max=200)),
            vol.Optional("quantity"): vol.All(str, vol.Length(max=80)),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Add the item and return the created record id."""
        client = _get_client(hass)
        if client is None:
            return _not_configured()
        name = tool_input.tool_args["name"]
        quantity = tool_input.tool_args.get("quantity")
        try:
            created = await client.async_add_shopping_item(name=name, quantity=quantity)
        except CuliplanApiError as err:
            return {"error": "api_error", "message": str(err)}
        return {
            "added": True,
            "name": name,
            "quantity": quantity,
            "item_id": created.get("id") if isinstance(created, dict) else None,
        }


class _GetPantryItemsTool(llm.Tool):
    """Return the user's pantry stock."""

    name = "get_pantry_items"
    description = (
        "Return the user's pantry stock. Optional expiring_within_days "
        "filters to items expiring in that many days."
    )
    parameters = vol.Schema(
        {
            vol.Optional("expiring_within_days"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=365)
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Fetch pantry stock and optionally filter by expiry."""
        client = _get_client(hass)
        if client is None:
            return _not_configured()
        try:
            items = await client.async_get_pantry_items()
        except CuliplanApiError as err:
            return {"error": "api_error", "message": str(err)}

        within_days = tool_input.tool_args.get("expiring_within_days")
        if within_days is not None:
            items = _filter_expiring(items, int(within_days))

        slimmed = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
                "expires_at": item.get("expiresAt"),
            }
            for item in items[:50]
            if isinstance(item, dict)
        ]
        return cast(
            JsonObjectType,
            {
                "pantry_items": slimmed,
                "count": len(slimmed),
                "truncated": len(items) > 50,
            },
        )


class _FindRecipesByIngredientsTool(llm.Tool):
    """Search recipes by ingredient list."""

    name = "find_recipes_by_ingredients"
    description = (
        "Find recipes the user can make from a list of ingredients. "
        "Returns up to 10 matches."
    )
    parameters = vol.Schema(
        {vol.Required("ingredients"): vol.All([str], vol.Length(min=1, max=20))}
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Search and trim the result to the LLM-relevant fields."""
        client = _get_client(hass)
        if client is None:
            return _not_configured()
        ingredients = tool_input.tool_args["ingredients"]
        query = ",".join(ingredients)
        path = f"/api/recipes?ingredients={quote(query)}&limit=10"
        try:
            result = await client.async_get(path)
        except CuliplanApiError as err:
            return {"error": "api_error", "message": str(err)}

        recipes_raw: Any
        if isinstance(result, dict) and "data" in result:
            recipes_raw = result["data"]
        elif isinstance(result, list):
            recipes_raw = result
        else:
            recipes_raw = []

        recipes: list[dict[str, Any]] = []
        if isinstance(recipes_raw, list):
            for r in recipes_raw[:10]:
                if not isinstance(r, dict):
                    continue
                recipes.append(
                    {
                        "id": r.get("id"),
                        "title": r.get("title"),
                        "prep_time_minutes": r.get("prepTime")
                        or r.get("prepTimeMinutes"),
                        "servings": r.get("servings"),
                    }
                )

        return {
            "recipes": recipes,
            "count": len(recipes),
            "ingredients_searched": ingredients,
        }


class _GetRecipeTool(llm.Tool):
    """Fetch a single recipe by id."""

    name = "get_recipe"
    description = (
        "Fetch full details for a recipe by id. Use the recipe_id "
        "returned by find_recipes_by_ingredients or get_meal_plan."
    )
    parameters = vol.Schema(
        {vol.Required("recipe_id"): vol.All(str, vol.Length(min=1, max=200))}
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Fetch the recipe and trim fields the LLM does not need."""
        client = _get_client(hass)
        if client is None:
            return _not_configured()
        recipe_id = tool_input.tool_args["recipe_id"]
        try:
            recipe = await client.async_get(f"/api/recipes/{quote(recipe_id, safe='')}")
        except CuliplanApiError as err:
            return {"error": "api_error", "message": str(err)}
        if not isinstance(recipe, dict):
            return {
                "error": "not_found",
                "message": f"No recipe found for id '{recipe_id}'.",
            }
        keep_keys = {
            "id",
            "title",
            "description",
            "ingredients",
            "instructions",
            "prepTime",
            "cookTime",
            "totalTime",
            "servings",
            "cuisine",
            "tags",
        }
        trimmed = {k: v for k, v in recipe.items() if k in keep_keys}
        return {"recipe": trimmed}


def _slot_in_range(date_value: Any, start: str | None, end: str | None) -> bool:
    """Return ``True`` if a slot's date falls within ``[start, end]``."""
    if not isinstance(date_value, str):
        return True
    date_only = date_value[:10]
    if start and date_only < start:
        return False
    return not (end and date_only > end)


def _filter_expiring(
    items: list[dict[str, Any]], within_days: int
) -> list[dict[str, Any]]:
    """Return only items expiring within ``within_days`` days."""
    now = datetime.now(tz=UTC)
    cutoff = now + timedelta(days=within_days)
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        expires_raw = item.get("expiresAt")
        if not isinstance(expires_raw, str):
            continue
        try:
            expires = datetime.fromisoformat(expires_raw)
        except ValueError:
            continue
        if expires <= cutoff:
            out.append(item)
    return out


@callback
def async_register_llm_api(hass: HomeAssistant) -> None:
    """Register the Culiplan LLM API (refcounted across config entries).

    The LLM API is a process-wide singleton, but each config entry that
    sets it up holds a reference. We register on the first entry and
    only unregister when the last entry is unloaded. This avoids the
    silent "API disappeared from one entry's unload" bug.
    """
    count = cast(int, hass.data.get(_LLM_REFCOUNT_KEY, 0))
    if count == 0:
        unregister = llm.async_register_api(hass, CuliplanLLMAPI(hass))
        hass.data[_LLM_UNREGISTER_KEY] = unregister
    hass.data[_LLM_REFCOUNT_KEY] = count + 1


@callback
def async_unregister_llm_api(hass: HomeAssistant) -> None:
    """Drop one reference; unregister the API when the last is gone."""
    count = cast(int, hass.data.get(_LLM_REFCOUNT_KEY, 0))
    if count <= 0:
        return
    count -= 1
    hass.data[_LLM_REFCOUNT_KEY] = count
    if count > 0:
        return
    unregister = cast(
        "Callable[[], None] | None", hass.data.pop(_LLM_UNREGISTER_KEY, None)
    )
    if unregister is not None:
        unregister()
