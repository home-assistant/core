"""Folder registry provides a folder structure for other integration to leverage."""
from __future__ import annotations

from collections.abc import Iterable, MutableMapping
import dataclasses
from dataclasses import dataclass, field
from typing import cast

from homeassistant.core import HomeAssistant, callback
import homeassistant.util.uuid as uuid_util

from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "folder_registry"
EVENT_FOLDER_REGISTRY_UPDATED = "folder_registry_updated"
STORAGE_KEY = "core.folder_registry"
STORAGE_VERSION_MAJOR = 1
SAVE_DELAY = 10


@dataclass(slots=True, frozen=True)
class FolderEntry:
    """Folder Registry Entry."""

    domain: str

    name: str
    normalized_name: str

    folder_id: str = field(default_factory=uuid_util.random_uuid_hex)

    # Meta
    icon: str | None = None


class FolderRegistry:
    """Class to hold a registry of folder."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the folder registry."""
        self.hass = hass
        self.folders: MutableMapping[str, FolderEntry] = {}
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
        )
        self._folder_idx: dict[str, dict[str, FolderEntry]] = {}

    @callback
    def async_get_folder(self, folder_id: str) -> FolderEntry | None:
        """Get folder by id."""
        return self.folders.get(folder_id)

    @callback
    def async_get_folder_by_name(self, domain: str, name: str) -> FolderEntry | None:
        """Get folder by name."""
        if domain not in self._folder_idx:
            return None

        normalized_name = normalize_name(name)
        if normalized_name not in self._folder_idx[domain]:
            return None

        return self._folder_idx[domain][normalized_name]

    @callback
    def async_list_folders(self, domain: str) -> Iterable[FolderEntry]:
        """Get all folders."""
        if domain not in self._folder_idx:
            return []
        return self._folder_idx[domain].values()

    @callback
    def async_get_or_create(self, domain: str, name: str) -> FolderEntry:
        """Get or create an folder."""
        if folder := self.async_get_folder_by_name(domain, name):
            return folder
        return self.async_create(domain, name)

    @callback
    def async_create(
        self,
        domain: str,
        name: str,
        *,
        icon: str | None = None,
    ) -> FolderEntry:
        """Create a new folder."""
        if folder_entry := self.async_get_folder_by_name(domain, name):
            raise ValueError(
                f"The name {name} ({folder_entry.normalized_name}) is already in use"
            )

        folder = FolderEntry(
            domain=domain,
            icon=icon,
            name=name,
            normalized_name=normalize_name(name),
        )
        self.folders[folder.folder_id] = folder
        if domain not in self._folder_idx:
            self._folder_idx[domain] = {}
        self._folder_idx[domain][folder.normalized_name] = folder
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FOLDER_REGISTRY_UPDATED,
            {"action": "create", "domain": domain, "folder_id": folder.folder_id},
        )
        return folder

    @callback
    def async_delete(self, folder_id: str) -> None:
        """Delete a folder."""
        folder = self.folders[folder_id]

        del self.folders[folder_id]
        del self._folder_idx[folder.domain][folder.normalized_name]

        self.hass.bus.async_fire(
            EVENT_FOLDER_REGISTRY_UPDATED,
            {"action": "remove", "domain": folder.domain, "folder_id": folder_id},
        )

        self.async_schedule_save()

    @callback
    def async_update(
        self,
        folder_id: str,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> FolderEntry:
        """Update name of a folder."""
        old = self.folders[folder_id]
        changes: dict[str, str | None] = {}

        normalized_name = None
        if name is not UNDEFINED and name != old.name:
            normalized_name = normalize_name(name)
            if (
                normalized_name != old.normalized_name
                and self.async_get_folder_by_name(old.domain, name)
            ):
                raise ValueError(
                    f"The name {name} ({normalized_name}) is already in use"
                )

            changes["name"] = name
            changes["normalized_name"] = normalized_name

        if icon is not UNDEFINED and icon != old.icon:
            changes["icon"] = icon

        if not changes:
            return old

        new = self.folders[folder_id] = dataclasses.replace(old, **changes)
        if normalized_name is not None:
            self._folder_idx[new.domain][normalized_name] = self._folder_idx[
                old.domain
            ].pop(old.normalized_name)

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_FOLDER_REGISTRY_UPDATED,
            {"action": "update", "domain": new.domain, "folder_id": folder_id},
        )

        return new

    async def async_load(self) -> None:
        """Load the folder registry."""
        data = await self._store.async_load()
        if data is not None:
            for folder_data in data["folders"]:
                folder = FolderEntry(
                    domain=folder_data["domain"],
                    folder_id=folder_data["folder_id"],
                    icon=folder_data["icon"],
                    name=folder_data["name"],
                    normalized_name=normalize_name(folder_data["name"]),
                )
                if folder.domain not in self._folder_idx:
                    self._folder_idx[folder.domain] = {}
                self.folders[folder.folder_id] = folder
                self._folder_idx[folder.domain][folder.normalized_name] = folder

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the folder registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of folder registry to store in a file."""
        return {
            "folders": [
                {
                    "domain": entry.domain,
                    "icon": entry.icon,
                    "folder_id": entry.folder_id,
                    "name": entry.name,
                }
                for entry in self.folders.values()
            ]
        }


@callback
def async_get(hass: HomeAssistant) -> FolderRegistry:
    """Get folder registry."""
    return cast(FolderRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load folder registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = FolderRegistry(hass)

    await hass.data[DATA_REGISTRY].async_load()


def normalize_name(name: str) -> str:
    """Normalize an folder name by removing whitespace and case folding."""
    return name.casefold().replace(" ", "")
