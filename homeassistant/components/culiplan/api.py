"""OAuth-aware async HTTP client for the Culiplan API.

The client only exposes the surface needed by the Core integration:

* GET meal plans, shopping list, pantry items
* mutate shopping list (add / check / delete)

Premium-only endpoints (energy, AI dispatchers, BYOK key validation) are
intentionally absent — those live in the standalone HACS distribution.
"""

import logging
from typing import Any, Final, cast

from aiohttp import ClientError, ClientSession, ClientTimeout

from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import BASE_URL

_LOGGER = logging.getLogger(__name__)

# Explicit per-request timeout for every REST call. aiohttp's default
# (5 minutes total) is far too lenient for a coordinator that polls every
# 5 minutes — a stuck request would stall the entire update cycle. Home
# Assistant Core reviewers require explicit timeouts on every HTTP call.
_API_TIMEOUT: Final = ClientTimeout(total=30)


class CuliplanApiError(Exception):
    """Generic Culiplan API error (non-auth)."""


class CuliplanApiClient:
    """Thin OAuth-aware client for the Culiplan REST API."""

    def __init__(self, session: ClientSession, access_token: str) -> None:
        """Store the shared aiohttp session and the current bearer token."""
        self._session = session
        self._access_token = access_token

    def set_access_token(self, token: str) -> None:
        """Replace the bearer token after a refresh."""
        self._access_token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ─── Read ────────────────────────────────────────────────────────────────

    async def async_get_meal_plans(self) -> list[dict[str, Any]]:
        """Return the user's meal plan as a single-element list.

        The backend groups slots by date:

            { "<YYYY-MM-DD>": { "<slot>": [<entry>, …], … }, … }

        We flatten that into one synthetic plan with id ``"current"`` so
        the calendar entity identity is stable across refreshes.
        """
        raw = await self._get("/api/meal-plans")

        # Legacy / test-double path: bare list already in the expected shape.
        if isinstance(raw, list):
            return cast(list[dict[str, Any]], raw)

        if not isinstance(raw, dict):
            _LOGGER.debug(
                "async_get_meal_plans: unexpected response type %s", type(raw)
            )
            return []

        slots: list[dict[str, Any]] = []
        for date_str, slots_by_name in raw.items():
            if not isinstance(slots_by_name, dict):
                continue
            for slot_name, entries in slots_by_name.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    entry_date: Any = entry.get("date") or f"{date_str}T12:00:00Z"
                    if not isinstance(entry_date, str):
                        entry_date = str(entry_date)
                    recipe = entry.get("recipe") or {}
                    title: str = recipe.get("title") or entry.get("title") or slot_name
                    slots.append(
                        {
                            "id": entry.get("id", f"{date_str}-{slot_name}"),
                            "date": entry_date,
                            "title": title,
                            "course": entry.get("mealSlot", slot_name),
                            "recipeId": entry.get("recipeId"),
                            "servings": entry.get("servings"),
                        }
                    )

        return [{"id": "current", "name": "Meal Plan", "slots": slots}]

    async def async_get_shopping_lists(self) -> list[dict[str, Any]]:
        """Return the user's shopping list wrapped as a single-element list."""
        items = await self._get("/api/shopping-list")
        return [{"id": "default", "name": "Shopping List", "items": items}]

    async def async_get_pantry_items(self) -> list[dict[str, Any]]:
        """Return the user's pantry stock as a flat list."""
        response = await self._get("/api/pantry/stock?limit=100")
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            return cast(list[dict[str, Any]], response["data"])
        if isinstance(response, list):
            return cast(list[dict[str, Any]], response)
        return []

    async def async_get_user(self) -> dict[str, Any]:
        """Return the authenticated user's profile (used for unique_id)."""
        return cast(dict[str, Any], await self._get("/api/users/me"))

    async def async_get(self, path: str) -> Any:
        """Run an arbitrary GET against the Culiplan API (used by LLM tools)."""
        return await self._get(path)

    # ─── Shopping list mutations ─────────────────────────────────────────────

    async def async_add_shopping_item(
        self, name: str, quantity: str | None = None
    ) -> dict[str, Any]:
        """Add an item to the shopping list."""
        item: dict[str, Any] = {"name": name}
        if quantity:
            item["quantity"] = quantity
        created = await self._post("/api/shopping-list", {"items": [item]})
        if isinstance(created, list) and created:
            return cast(dict[str, Any], created[0])
        return cast(dict[str, Any], created)

    async def async_update_shopping_item(
        self, item_id: str, completed: bool
    ) -> dict[str, Any]:
        """Toggle the ``completed`` state of a shopping-list item."""
        return cast(
            dict[str, Any],
            await self._patch(f"/api/shopping-list/{item_id}", {"checked": completed}),
        )

    async def async_remove_shopping_item(self, item_id: str) -> None:
        """Delete a shopping-list item."""
        await self._delete(f"/api/shopping-list/{item_id}")

    # ─── HTTP helpers ────────────────────────────────────────────────────────

    async def _get(self, path: str) -> Any:
        try:
            async with self._session.get(
                f"{BASE_URL}{path}",
                headers=self._headers(),
                timeout=_API_TIMEOUT,
            ) as resp:
                self._raise_for_status(resp.status, path)
                resp.raise_for_status()
                return await resp.json()
        except TimeoutError as err:
            raise CuliplanApiError(f"GET {path} timed out") from err
        except ClientError as err:
            raise CuliplanApiError(f"GET {path} failed: {err}") from err

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with self._session.post(
                f"{BASE_URL}{path}",
                headers=self._headers(),
                json=payload,
                timeout=_API_TIMEOUT,
            ) as resp:
                self._raise_for_status(resp.status, path)
                resp.raise_for_status()
                return await resp.json()
        except TimeoutError as err:
            raise CuliplanApiError(f"POST {path} timed out") from err
        except ClientError as err:
            raise CuliplanApiError(f"POST {path} failed: {err}") from err

    async def _patch(self, path: str, payload: dict[str, Any]) -> Any:
        try:
            async with self._session.patch(
                f"{BASE_URL}{path}",
                headers=self._headers(),
                json=payload,
                timeout=_API_TIMEOUT,
            ) as resp:
                self._raise_for_status(resp.status, path)
                resp.raise_for_status()
                return await resp.json()
        except TimeoutError as err:
            raise CuliplanApiError(f"PATCH {path} timed out") from err
        except ClientError as err:
            raise CuliplanApiError(f"PATCH {path} failed: {err}") from err

    async def _delete(self, path: str) -> None:
        try:
            async with self._session.delete(
                f"{BASE_URL}{path}",
                headers=self._headers(),
                timeout=_API_TIMEOUT,
            ) as resp:
                self._raise_for_status(resp.status, path)
                resp.raise_for_status()
        except TimeoutError as err:
            raise CuliplanApiError(f"DELETE {path} timed out") from err
        except ClientError as err:
            raise CuliplanApiError(f"DELETE {path} failed: {err}") from err

    @staticmethod
    def _raise_for_status(status: int, path: str) -> None:
        """Map 401 onto ``ConfigEntryAuthFailed`` so HA triggers re-auth."""
        if status == 401:
            raise ConfigEntryAuthFailed(
                f"Culiplan token expired or revoked (401 on {path})"
            )
