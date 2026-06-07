"""Tests for the Culiplan REST API client."""

from typing import Any

import aiohttp
from aioresponses import aioresponses
import pytest

from homeassistant.components.culiplan.api import CuliplanApiClient, CuliplanApiError
from homeassistant.components.culiplan.const import BASE_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import aiohttp_client


@pytest.fixture
def mock_aioresponses() -> Any:
    """Yield an aioresponses fixture."""
    with aioresponses() as m:
        yield m


async def test_get_meal_plans_normalises_grouped_dict(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A grouped-dict response is flattened into one synthetic plan."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/meal-plans",
        payload={
            "2099-01-15": {
                "dinner": [
                    {
                        "id": "slot-1",
                        "date": "2099-01-15T18:00:00Z",
                        "recipe": {"title": "Spaghetti"},
                        "recipeId": "recipe-1",
                        "mealSlot": "dinner",
                    }
                ]
            }
        },
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    plans = await client.async_get_meal_plans()
    assert len(plans) == 1
    assert plans[0]["id"] == "current"
    assert len(plans[0]["slots"]) == 1
    assert plans[0]["slots"][0]["title"] == "Spaghetti"


async def test_get_meal_plans_passthrough_list(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A bare list response is returned as-is."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/meal-plans",
        payload=[{"id": "p", "slots": []}],
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    plans = await client.async_get_meal_plans()
    assert plans == [{"id": "p", "slots": []}]


async def test_get_meal_plans_unexpected_type(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """An unexpected payload type returns an empty list."""
    mock_aioresponses.get(f"{BASE_URL}/api/meal-plans", payload="oops")
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    plans = await client.async_get_meal_plans()
    assert plans == []


async def test_get_shopping_lists_wraps(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """The shopping list is wrapped in a one-element list."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/shopping-list",
        payload=[{"id": "i1", "name": "Milk", "completed": False}],
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    lists = await client.async_get_shopping_lists()
    assert lists[0]["id"] == "default"
    assert lists[0]["items"][0]["name"] == "Milk"


async def test_get_pantry_items_envelope_and_list(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Pantry parser handles both envelope and bare list."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")

    mock_aioresponses.get(
        f"{BASE_URL}/api/pantry/stock?limit=100",
        payload={"data": [{"id": "p1"}]},
    )
    assert await client.async_get_pantry_items() == [{"id": "p1"}]

    mock_aioresponses.get(
        f"{BASE_URL}/api/pantry/stock?limit=100",
        payload=[{"id": "p2"}],
    )
    assert await client.async_get_pantry_items() == [{"id": "p2"}]

    mock_aioresponses.get(
        f"{BASE_URL}/api/pantry/stock?limit=100",
        payload="unexpected",
    )
    assert await client.async_get_pantry_items() == []


async def test_401_raises_auth_failed(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A 401 is mapped onto ConfigEntryAuthFailed."""
    mock_aioresponses.get(f"{BASE_URL}/api/shopping-list", status=401)
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(ConfigEntryAuthFailed):
        await client.async_get_shopping_lists()


async def test_5xx_raises_api_error(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A 5xx raises CuliplanApiError."""
    mock_aioresponses.get(f"{BASE_URL}/api/shopping-list", status=500)
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError):
        await client.async_get_shopping_lists()


async def test_network_error_raises_api_error(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Connection errors raise CuliplanApiError."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/shopping-list",
        exception=aiohttp.ClientError("boom"),
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError):
        await client.async_get_shopping_lists()


async def test_shopping_list_mutations(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Add / update / delete return parsed payloads."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")

    mock_aioresponses.post(
        f"{BASE_URL}/api/shopping-list",
        payload=[{"id": "n1", "name": "Eggs"}],
    )
    created = await client.async_add_shopping_item("Eggs", quantity="6")
    assert created["id"] == "n1"

    mock_aioresponses.post(
        f"{BASE_URL}/api/shopping-list",
        payload={"id": "n2", "name": "Bread"},
    )
    created = await client.async_add_shopping_item("Bread")
    assert created["id"] == "n2"

    mock_aioresponses.patch(
        f"{BASE_URL}/api/shopping-list/n1",
        payload={"id": "n1", "completed": True},
    )
    updated = await client.async_update_shopping_item("n1", completed=True)
    assert updated["id"] == "n1"

    mock_aioresponses.delete(f"{BASE_URL}/api/shopping-list/n1", status=204)
    await client.async_remove_shopping_item("n1")


async def test_async_get_user_and_passthrough(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """``async_get_user`` and ``async_get`` work."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/users/me", payload={"id": "u1", "email": "x@y.z"}
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    me = await client.async_get_user()
    assert me["id"] == "u1"

    mock_aioresponses.get(f"{BASE_URL}/api/anything", payload={"ok": True})
    assert await client.async_get("/api/anything") == {"ok": True}


async def test_patch_and_delete_network_error(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Network errors during PATCH / DELETE raise CuliplanApiError."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    mock_aioresponses.patch(
        f"{BASE_URL}/api/shopping-list/x",
        exception=aiohttp.ClientError("net"),
    )
    with pytest.raises(CuliplanApiError):
        await client.async_update_shopping_item("x", completed=True)

    mock_aioresponses.delete(
        f"{BASE_URL}/api/shopping-list/x",
        exception=aiohttp.ClientError("net"),
    )
    with pytest.raises(CuliplanApiError):
        await client.async_remove_shopping_item("x")


async def test_post_network_error(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Network errors during POST raise CuliplanApiError."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    mock_aioresponses.post(
        f"{BASE_URL}/api/shopping-list",
        exception=aiohttp.ClientError("net"),
    )
    with pytest.raises(CuliplanApiError):
        await client.async_add_shopping_item("Eggs")


async def test_get_meal_plans_malformed_inner_entries(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """Malformed nested data is silently skipped."""
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    mock_aioresponses.get(
        f"{BASE_URL}/api/meal-plans",
        payload={
            "2099-01-15": {
                "dinner": [
                    "not-a-dict",
                    {"id": "ok", "date": 12345},  # non-string date coerced
                ],
                "lunch": "not-a-list",
            },
            "bad-date": "not-a-dict",
        },
    )
    plans = await client.async_get_meal_plans()
    assert plans[0]["id"] == "current"
    # Only the salvageable entry survives.
    assert len(plans[0]["slots"]) == 1


def test_set_access_token() -> None:
    """``set_access_token`` updates the bearer."""
    client = CuliplanApiClient(session=None, access_token="old")  # type: ignore[arg-type]
    client.set_access_token("new")
    assert client._access_token == "new"


async def test_api_timeout_raises_api_error_get(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A timeout on GET surfaces as ``CuliplanApiError`` (mapped to UpdateFailed)."""
    mock_aioresponses.get(
        f"{BASE_URL}/api/shopping-list",
        exception=TimeoutError("slow"),
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError, match="timed out"):
        await client.async_get_shopping_lists()


async def test_api_timeout_raises_api_error_post(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A timeout on POST surfaces as ``CuliplanApiError``."""
    mock_aioresponses.post(
        f"{BASE_URL}/api/shopping-list",
        exception=TimeoutError("slow"),
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError, match="timed out"):
        await client.async_add_shopping_item("Eggs")


async def test_api_timeout_raises_api_error_patch(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A timeout on PATCH surfaces as ``CuliplanApiError``."""
    mock_aioresponses.patch(
        f"{BASE_URL}/api/shopping-list/x",
        exception=TimeoutError("slow"),
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError, match="timed out"):
        await client.async_update_shopping_item("x", completed=True)


async def test_api_timeout_raises_api_error_delete(
    hass: HomeAssistant, mock_aioresponses: aioresponses
) -> None:
    """A timeout on DELETE surfaces as ``CuliplanApiError``."""
    mock_aioresponses.delete(
        f"{BASE_URL}/api/shopping-list/x",
        exception=TimeoutError("slow"),
    )
    session = aiohttp_client.async_get_clientsession(hass)
    client = CuliplanApiClient(session, "token")
    with pytest.raises(CuliplanApiError, match="timed out"):
        await client.async_remove_shopping_item("x")
