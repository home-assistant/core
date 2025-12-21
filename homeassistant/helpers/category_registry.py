"""Provide a way to categorize things within a defined scope."""

from __future__ import annotations

from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, TypedDict

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util.dt import utc_from_timestamp, utcnow
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey
from homeassistant.util.ulid import ulid_now

from .registry import BaseRegistry
from .singleton import singleton
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY: HassKey[CategoryRegistry] = HassKey("category_registry")
EVENT_CATEGORY_REGISTRY_UPDATED: EventType[EventCategoryRegistryUpdatedData] = (
    EventType("category_registry_updated")
)
STORAGE_KEY = "core.category_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2


class _CategoryStoreData(TypedDict):
    """Data type for individual category. Used in CategoryRegistryStoreData."""

    category_id: str
    created_at: str
    icon: str | None
    modified_at: str
    name: str


class CategoryRegistryStoreData(TypedDict):
    """Store data type for CategoryRegistry."""

    categories: dict[str, list[_CategoryStoreData]]


class EventCategoryRegistryUpdatedData(TypedDict):
    """Event data for when the category registry is updated."""

    action: Literal["create", "remove", "update"]
    scope: str
    category_id: str


type EventCategoryRegistryUpdated = Event[EventCategoryRegistryUpdatedData]


@dataclass(slots=True, kw_only=True, frozen=True)
class CategoryEntry:
    """Category registry entry."""

    category_id: str = field(default_factory=ulid_now)
    created_at: datetime = field(default_factory=utcnow)
    icon: str | None = None
    modified_at: datetime = field(default_factory=utcnow)
    name: str


class CategoryRegistryStore(Store[CategoryRegistryStoreData]):
    """Store category registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, dict[str, list[dict[str, Any]]]],
    ) -> CategoryRegistryStoreData:
        """Migrate to the new version."""
        if old_major_version > STORAGE_VERSION_MAJOR:
            raise ValueError("Can't migrate to future version")

        if old_major_version == 1:
            if old_minor_version < 2:
                # Version 1.2 implements migration and adds created_at and modified_at
                created_at = utc_from_timestamp(0).isoformat()
                for categories in old_data["categories"].values():
                    for category in categories:
                        category["created_at"] = category["modified_at"] = created_at

        return old_data  # type: ignore[return-value]


class CategoryRegistry(BaseRegistry[CategoryRegistryStoreData]):
    """Class to hold a registry of categories by scope."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the category registry."""
        self.hass = hass
        self.categories: dict[str, dict[str, CategoryEntry]] = {}
        self._store = CategoryRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
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
        self.hass.verify_event_loop_thread("category_registry.async_create")
        self._async_ensure_name_is_available(scope, name)
        category = CategoryEntry(
            icon=icon,
            name=name,
        )

        if scope not in self.categories:
            self.categories[scope] = {}

        self.categories[scope][category.category_id] = category

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_CATEGORY_REGISTRY_UPDATED,
            EventCategoryRegistryUpdatedData(
                action="create", scope=scope, category_id=category.category_id
            ),
        )
        return category

    @callback
    def async_delete(self, *, scope: str, category_id: str) -> None:
        """Delete category."""
        self.hass.verify_event_loop_thread("category_registry.async_delete")
        del self.categories[scope][category_id]
        self.hass.bus.async_fire_internal(
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
        changes: dict[str, Any] = {}

        if icon is not UNDEFINED and icon != old.icon:
            changes["icon"] = icon

        if name is not UNDEFINED and name != old.name:
            changes["name"] = name
            self._async_ensure_name_is_available(scope, name, category_id)

        if not changes:
            return old

        changes["modified_at"] = utcnow()

        self.hass.verify_event_loop_thread("category_registry.async_update")
        new = self.categories[scope][category_id] = dataclasses.replace(old, **changes)

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
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
                        created_at=datetime.fromisoformat(category["created_at"]),
                        icon=category["icon"],
                        modified_at=datetime.fromisoformat(category["modified_at"]),
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
                        "created_at": entry.created_at.isoformat(),
                        "icon": entry.icon,
                        "modified_at": entry.modified_at.isoformat(),
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
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> CategoryRegistry:
    """Get category registry."""
    return CategoryRegistry(hass)


async def async_load(hass: HomeAssistant) -> None:
    """Load category registry."""
    assert DATA_REGISTRY not in hass.data
    await async_get(hass).async_load()
