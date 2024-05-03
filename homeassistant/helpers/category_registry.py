"""Provide a way to categorize things within a defined scope."""

from __future__ import annotations

from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass, field
from typing import Literal, TypedDict, cast

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.event_type import EventType
from homeassistant.util.ulid import ulid_now

from .registry import BaseRegistry
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "category_registry"
EVENT_CATEGORY_REGISTRY_UPDATED: EventType[EventCategoryRegistryUpdatedData] = (
    EventType("category_registry_updated")
)
STORAGE_KEY = "core.category_registry"
STORAGE_VERSION_MAJOR = 1


class _CategoryStoreData(TypedDict):
    """Data type for individual category. Used in CategoryRegistryStoreData."""

    category_id: str
    icon: str | None
    name: str


class CategoryRegistryStoreData(TypedDict):
    """Store data type for CategoryRegistry."""

    categories: dict[str, list[_CategoryStoreData]]


class EventCategoryRegistryUpdatedData(TypedDict):
    """Event data for when the category registry is updated."""

    action: Literal["create", "remove", "update"]
    scope: str
    category_id: str


EventCategoryRegistryUpdated = Event[EventCategoryRegistryUpdatedData]


@dataclass(slots=True, kw_only=True, frozen=True)
class CategoryEntry:
    """Category registry entry."""

    category_id: str = field(default_factory=ulid_now)
    icon: str | None = None
    name: str


class CategoryRegistry(BaseRegistry[CategoryRegistryStoreData]):
    """Class to hold a registry of categories by scope."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the category registry."""
        self.hass = hass
        self.categories: dict[str, dict[str, CategoryEntry]] = {}
        self._store = Store(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
        )

    @callback
    def async_get_category(
        self, *, scope: str, category_id: str
    ) -> CategoryEntry | None:
        """Get category by ID."""
        if scope not in self.categories:
            return None
        return self.categories[scope].get(category_id)

    @callback
    def async_list_categories(self, *, scope: str) -> Iterable[CategoryEntry]:
        """Get all categories."""
        if scope not in self.categories:
            return []
        return self.categories[scope].values()

    @callback
    def async_create(
        self,
        *,
        name: str,
        scope: str,
        icon: str | None = None,
    ) -> CategoryEntry:
        """Create a new category."""
        self._async_ensure_name_is_available(scope, name)
        category = CategoryEntry(
            icon=icon,
            name=name,
        )

        if scope not in self.categories:
            self.categories[scope] = {}

        self.categories[scope][category.category_id] = category

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_CATEGORY_REGISTRY_UPDATED,
            EventCategoryRegistryUpdatedData(
                action="create", scope=scope, category_id=category.category_id
            ),
        )
        return category

    @callback
    def async_delete(self, *, scope: str, category_id: str) -> None:
        """Delete category."""
        del self.categories[scope][category_id]
        self.hass.bus.async_fire(
            EVENT_CATEGORY_REGISTRY_UPDATED,
            EventCategoryRegistryUpdatedData(
                action="remove",
                scope=scope,
                category_id=category_id,
            ),
        )
        self.async_schedule_save()

    @callback
    def async_update(
        self,
        *,
        scope: str,
        category_id: str,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> CategoryEntry:
        """Update name or icon of the category."""
        old = self.categories[scope][category_id]
        changes = {}

        if icon is not UNDEFINED and icon != old.icon:
            changes["icon"] = icon

        if name is not UNDEFINED and name != old.name:
            changes["name"] = name
            self._async_ensure_name_is_available(scope, name, category_id)

        if not changes:
            return old

        new = self.categories[scope][category_id] = dataclasses.replace(old, **changes)  # type: ignore[arg-type]

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_CATEGORY_REGISTRY_UPDATED,
            EventCategoryRegistryUpdatedData(
                action="update", scope=scope, category_id=category_id
            ),
        )

        return new

    async def async_load(self) -> None:
        """Load the category registry."""
        data = await self._store.async_load()
        category_entries: dict[str, dict[str, CategoryEntry]] = {}

        if data is not None:
            for scope, categories in data["categories"].items():
                category_entries[scope] = {
                    category["category_id"]: CategoryEntry(
                        category_id=category["category_id"],
                        icon=category["icon"],
                        name=category["name"],
                    )
                    for category in categories
                }

        self.categories = category_entries

    @callback
    def _data_to_save(self) -> CategoryRegistryStoreData:
        """Return data of category registry to store in a file."""
        return {
            "categories": {
                scope: [
                    {
                        "category_id": entry.category_id,
                        "icon": entry.icon,
                        "name": entry.name,
                    }
                    for entry in entries.values()
                ]
                for scope, entries in self.categories.items()
            }
        }

    @callback
    def _async_ensure_name_is_available(
        self, scope: str, name: str, category_id: str | None = None
    ) -> None:
        """Ensure name is available within the scope."""
        if scope not in self.categories:
            return
        for category in self.categories[scope].values():
            if (
                category.name.casefold() == name.casefold()
                and category.category_id != category_id
            ):
                raise ValueError(f"The name '{name}' is already in use")


@callback
def async_get(hass: HomeAssistant) -> CategoryRegistry:
    """Get category registry."""
    return cast(CategoryRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load category registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = CategoryRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()
