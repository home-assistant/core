"""Provide a way to label and group anything."""

from __future__ import annotations

from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypedDict

from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.util import slugify
from homeassistant.util.dt import utc_from_timestamp, utcnow
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey

from .normalized_name_base_registry import (
    NormalizedNameBaseRegistryEntry,
    NormalizedNameBaseRegistryItems,
    normalize_name,
)
from .registry import BaseRegistry
from .singleton import singleton
from .storage import Store
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY: HassKey[LabelRegistry] = HassKey("label_registry")
EVENT_LABEL_REGISTRY_UPDATED: EventType[EventLabelRegistryUpdatedData] = EventType(
    "label_registry_updated"
)
STORAGE_KEY = "core.label_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 2


class _LabelStoreData(TypedDict):
    """Data type for individual label. Used in LabelRegistryStoreData."""

    color: str | None
    description: str | None
    icon: str | None
    label_id: str
    name: str
    created_at: str
    modified_at: str


class LabelRegistryStoreData(TypedDict):
    """Store data type for LabelRegistry."""

    labels: list[_LabelStoreData]


class EventLabelRegistryUpdatedData(TypedDict):
    """Event data for when the label registry is updated."""

    action: Literal["create", "remove", "update"]
    label_id: str


type EventLabelRegistryUpdated = Event[EventLabelRegistryUpdatedData]


@dataclass(slots=True, frozen=True, kw_only=True)
class LabelEntry(NormalizedNameBaseRegistryEntry):
    """Label Registry Entry."""

    label_id: str
    description: str | None = None
    color: str | None = None
    icon: str | None = None


class LabelRegistryStore(Store[LabelRegistryStoreData]):
    """Store label registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> LabelRegistryStoreData:
        """Migrate to the new version."""
        if old_major_version > STORAGE_VERSION_MAJOR:
            raise ValueError("Can't migrate to future version")

        if old_major_version == 1:
            if old_minor_version < 2:
                # Version 1.2 implements migration and adds created_at and modified_at
                created_at = utc_from_timestamp(0).isoformat()
                for label in old_data["labels"]:
                    label["created_at"] = label["modified_at"] = created_at

        return old_data  # type: ignore[return-value]


class LabelRegistry(BaseRegistry[LabelRegistryStoreData]):
    """Class to hold a registry of labels."""

    labels: NormalizedNameBaseRegistryItems[LabelEntry]
    _label_data: dict[str, LabelEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the label registry."""
        self.hass = hass
        self._store = LabelRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_get_label(self, label_id: str) -> LabelEntry | None:
        """Get label by ID.

        We retrieve the LabelEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._label_data.get(label_id)

    @callback
    def async_get_label_by_name(self, name: str) -> LabelEntry | None:
        """Get label by name."""
        return self.labels.get_by_name(name)

    @callback
    def async_list_labels(self) -> Iterable[LabelEntry]:
        """Get all labels."""
        return self.labels.values()

    @callback
    def _generate_id(self, name: str) -> str:
        """Initialize ID."""
        suggestion = suggestion_base = slugify(name)
        tries = 1
        while suggestion in self.labels:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        return suggestion

    @callback
    def async_create(
        self,
        name: str,
        *,
        color: str | None = None,
        icon: str | None = None,
        description: str | None = None,
    ) -> LabelEntry:
        """Create a new label."""
        self.hass.verify_event_loop_thread("label_registry.async_create")
        if label := self.async_get_label_by_name(name):
            raise ValueError(
                f"The name {name} ({label.normalized_name}) is already in use"
            )

        normalized_name = normalize_name(name)

        label = LabelEntry(
            color=color,
            description=description,
            icon=icon,
            label_id=self._generate_id(name),
            name=name,
            normalized_name=normalized_name,
        )
        label_id = label.label_id
        self.labels[label_id] = label
        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_LABEL_REGISTRY_UPDATED,
            EventLabelRegistryUpdatedData(
                action="create",
                label_id=label_id,
            ),
        )
        return label

    @callback
    def async_delete(self, label_id: str) -> None:
        """Delete label."""
        self.hass.verify_event_loop_thread("label_registry.async_delete")
        del self.labels[label_id]
        self.hass.bus.async_fire_internal(
            EVENT_LABEL_REGISTRY_UPDATED,
            EventLabelRegistryUpdatedData(
                action="remove",
                label_id=label_id,
            ),
        )
        self.async_schedule_save()

    @callback
    def async_update(
        self,
        label_id: str,
        *,
        color: str | None | UndefinedType = UNDEFINED,
        description: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> LabelEntry:
        """Update name of label."""
        old = self.labels[label_id]
        changes: dict[str, Any] = {
            attr_name: value
            for attr_name, value in (
                ("color", color),
                ("description", description),
                ("icon", icon),
            )
            if value is not UNDEFINED and getattr(old, attr_name) != value
        }

        if name is not UNDEFINED and name != old.name:
            changes["name"] = name
            changes["normalized_name"] = normalize_name(name)

        if not changes:
            return old

        changes["modified_at"] = utcnow()

        self.hass.verify_event_loop_thread("label_registry.async_update")
        new = self.labels[label_id] = dataclasses.replace(old, **changes)

        self.async_schedule_save()
        self.hass.bus.async_fire_internal(
            EVENT_LABEL_REGISTRY_UPDATED,
            EventLabelRegistryUpdatedData(
                action="update",
                label_id=label_id,
            ),
        )

        return new

    async def async_load(self) -> None:
        """Load the label registry."""
        data = await self._store.async_load()
        labels = NormalizedNameBaseRegistryItems[LabelEntry]()

        if data is not None:
            for label in data["labels"]:
                normalized_name = normalize_name(label["name"])
                labels[label["label_id"]] = LabelEntry(
                    color=label["color"],
                    description=label["description"],
                    icon=label["icon"],
                    label_id=label["label_id"],
                    name=label["name"],
                    normalized_name=normalized_name,
                    created_at=datetime.fromisoformat(label["created_at"]),
                    modified_at=datetime.fromisoformat(label["modified_at"]),
                )

        self.labels = labels
        self._label_data = labels.data

    @callback
    def _data_to_save(self) -> LabelRegistryStoreData:
        """Return data of label registry to store in a file."""
        return {
            "labels": [
                {
                    "color": entry.color,
                    "description": entry.description,
                    "icon": entry.icon,
                    "label_id": entry.label_id,
                    "name": entry.name,
                    "created_at": entry.created_at.isoformat(),
                    "modified_at": entry.modified_at.isoformat(),
                }
                for entry in self.labels.values()
            ]
        }


@callback
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> LabelRegistry:
    """Get label registry."""
    return LabelRegistry(hass)


async def async_load(hass: HomeAssistant) -> None:
    """Load label registry."""
    assert DATA_REGISTRY not in hass.data
    await async_get(hass).async_load()
