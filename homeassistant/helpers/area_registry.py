"""Provide a way to connect devices to one physical location."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
import dataclasses
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant, callback
from homeassistant.util.dt import utc_from_timestamp, utcnow
from homeassistant.util.event_type import EventType
from homeassistant.util.hass_dict import HassKey

from . import device_registry as dr, entity_registry as er
from .json import json_bytes, json_fragment
from .normalized_name_base_registry import (
    NormalizedNameBaseRegistryEntry,
    NormalizedNameBaseRegistryItems,
    normalize_name,
)
from .registry import BaseRegistry, RegistryIndexType
from .singleton import singleton
from .storage import Store
from .typing import UNDEFINED, UndefinedType

if TYPE_CHECKING:
    # mypy cannot workout _cache Protocol with dataclasses
    from propcache.api import cached_property as under_cached_property
else:
    from propcache.api import under_cached_property


DATA_REGISTRY: HassKey[AreaRegistry] = HassKey("area_registry")
EVENT_AREA_REGISTRY_UPDATED: EventType[EventAreaRegistryUpdatedData] = EventType(
    "area_registry_updated"
)
STORAGE_KEY = "core.area_registry"
STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 9


class _AreaStoreData(TypedDict):
    """Data type for individual area. Used in AreasRegistryStoreData."""

    aliases: list[str]
    floor_id: str | None
    humidity_entity_id: str | None
    icon: str | None
    id: str
    labels: list[str]
    motion_entity_id: str | None
    name: str
    picture: str | None
    temperature_entity_id: str | None
    created_at: str
    modified_at: str


class AreasRegistryStoreData(TypedDict):
    """Store data type for AreaRegistry."""

    areas: list[_AreaStoreData]


class EventAreaRegistryUpdatedData(TypedDict):
    """EventAreaRegistryUpdated data."""

    action: Literal["create", "remove", "update"]
    area_id: str


@dataclass(frozen=True, kw_only=True, slots=True)
class AreaEntry(NormalizedNameBaseRegistryEntry):
    """Area Registry Entry."""

    aliases: set[str]
    floor_id: str | None
    humidity_entity_id: str | None
    icon: str | None
    id: str
    labels: set[str] = field(default_factory=set)
    motion_entity_id: str | None
    picture: str | None
    temperature_entity_id: str | None
    _cache: dict[str, Any] = field(default_factory=dict, compare=False, init=False)

    @under_cached_property
    def json_fragment(self) -> json_fragment:
        """Return a JSON representation of this AreaEntry."""
        return json_fragment(
            json_bytes(
                {
                    "aliases": list(self.aliases),
                    "area_id": self.id,
                    "floor_id": self.floor_id,
                    "humidity_entity_id": self.humidity_entity_id,
                    "icon": self.icon,
                    "labels": list(self.labels),
                    "motion_entity_id": self.motion_entity_id,
                    "name": self.name,
                    "picture": self.picture,
                    "temperature_entity_id": self.temperature_entity_id,
                    "created_at": self.created_at.timestamp(),
                    "modified_at": self.modified_at.timestamp(),
                }
            )
        )


class AreaRegistryStore(Store[AreasRegistryStoreData]):
    """Store area registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> AreasRegistryStoreData:
        """Migrate to the new version."""
        if old_major_version < 2:
            if old_minor_version < 2:
                # Version 1.2 implements migration and freezes the available keys
                for area in old_data["areas"]:
                    # Populate keys which were introduced before version 1.2
                    area.setdefault("picture", None)

            if old_minor_version < 3:
                # Version 1.3 adds aliases
                for area in old_data["areas"]:
                    area["aliases"] = []

            if old_minor_version < 4:
                # Version 1.4 adds icon
                for area in old_data["areas"]:
                    area["icon"] = None

            if old_minor_version < 5:
                # Version 1.5 adds floor_id
                for area in old_data["areas"]:
                    area["floor_id"] = None

            if old_minor_version < 6:
                # Version 1.6 adds labels
                for area in old_data["areas"]:
                    area["labels"] = []

            if old_minor_version < 7:
                # Version 1.7 adds created_at and modified_at
                created_at = utc_from_timestamp(0).isoformat()
                for area in old_data["areas"]:
                    area["created_at"] = area["modified_at"] = created_at

            if old_minor_version < 8:
                # Version 1.8 adds humidity_entity_id and temperature_entity_id
                for area in old_data["areas"]:
                    area["humidity_entity_id"] = None
                    area["temperature_entity_id"] = None

            if old_minor_version < 9:
                # Version 1.9 adds motion_entity_id
                for area_data in old_data["areas"]:
                    area_data["motion_entity_id"] = None

        if old_major_version > 1:
            raise NotImplementedError
        return old_data  # type: ignore[return-value]


class AreaRegistryItems(NormalizedNameBaseRegistryItems[AreaEntry]):
    """Class to hold area registry items."""

    def __init__(self) -> None:
        """Initialize the area registry items."""
        super().__init__()
        self._labels_index: RegistryIndexType = defaultdict(dict)
        self._floors_index: RegistryIndexType = defaultdict(dict)
        self._aliases_index: RegistryIndexType = defaultdict(dict)

    def _index_entry(self, key: str, entry: AreaEntry) -> None:
        """Index an entry."""
        super()._index_entry(key, entry)
        if entry.floor_id is not None:
            self._floors_index[entry.floor_id][key] = True
        for label in entry.labels:
            self._labels_index[label][key] = True
        for alias in entry.aliases:
            normalized_alias = normalize_name(alias)
            self._aliases_index[normalized_alias][key] = True

    def _unindex_entry(
        self, key: str, replacement_entry: AreaEntry | None = None
    ) -> None:
        # always call base class before other indices
        super()._unindex_entry(key, replacement_entry)
        entry = self.data[key]
        if aliases := entry.aliases:
            for alias in aliases:
                normalized_alias = normalize_name(alias)
                self._unindex_entry_value(key, normalized_alias, self._aliases_index)
        if labels := entry.labels:
            for label in labels:
                self._unindex_entry_value(key, label, self._labels_index)
        if floor_id := entry.floor_id:
            self._unindex_entry_value(key, floor_id, self._floors_index)

    def get_areas_for_label(self, label: str) -> list[AreaEntry]:
        """Get areas for label."""
        data = self.data
        return [data[key] for key in self._labels_index.get(label, ())]

    def get_areas_for_floor(self, floor: str) -> list[AreaEntry]:
        """Get areas for floor."""
        data = self.data
        return [data[key] for key in self._floors_index.get(floor, ())]

    def get_areas_for_alias(self, alias: str) -> list[AreaEntry]:
        """Get areas for alias."""
        data = self.data
        normalized_alias = normalize_name(alias)
        return [data[key] for key in self._aliases_index.get(normalized_alias, ())]


class AreaRegistry(BaseRegistry[AreasRegistryStoreData]):
    """Class to hold a registry of areas."""

    areas: AreaRegistryItems
    _area_data: dict[str, AreaEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the area registry."""
        self.hass = hass
        self._store = AreaRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )

    @callback
    def async_get_area(self, area_id: str) -> AreaEntry | None:
        """Get area by id.

        We retrieve the DeviceEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._area_data.get(area_id)

    @callback
    def async_get_area_by_name(self, name: str) -> AreaEntry | None:
        """Get area by name."""
        return self.areas.get_by_name(name)

    @callback
    def async_get_areas_by_alias(self, alias: str) -> list[AreaEntry]:
        """Get areas by alias."""
        return self.areas.get_areas_for_alias(alias)

    @callback
    def async_list_areas(self) -> Iterable[AreaEntry]:
        """Get all areas."""
        return self.areas.values()

    @callback
    def async_get_or_create(self, name: str) -> AreaEntry:
        """Get or create an area."""
        if area := self.async_get_area_by_name(name):
            return area
        return self.async_create(name)

    def _generate_id(self, name: str) -> str:
        """Generate area ID."""
        return self.areas.generate_id_from_name(name)

    @callback
    def async_create(
        self,
        name: str,
        *,
        aliases: set[str] | None = None,
        floor_id: str | None = None,
        humidity_entity_id: str | None = None,
        icon: str | None = None,
        labels: set[str] | None = None,
        motion_entity_id: str | None = None,
        picture: str | None = None,
        temperature_entity_id: str | None = None,
    ) -> AreaEntry:
        """Create a new area."""

        self.hass.verify_event_loop_thread("area_registry.async_create")

        if area := self.async_get_area_by_name(name):
            raise ValueError(
                f"The name {name} ({area.normalized_name}) is already in use"
            )

        if humidity_entity_id is not None:
            _validate_humidity_entity(self.hass, humidity_entity_id)

        if motion_entity_id is not None:
            _validate_motion_entity(self.hass, motion_entity_id)

        if temperature_entity_id is not None:
            _validate_temperature_entity(self.hass, temperature_entity_id)

        area = AreaEntry(
            aliases=aliases or set(),
            floor_id=floor_id,
            humidity_entity_id=humidity_entity_id,
            icon=icon,
            id=self._generate_id(name),
            labels=labels or set(),
            motion_entity_id=motion_entity_id,
            name=name,
            picture=picture,
            temperature_entity_id=temperature_entity_id,
        )
        area_id = area.id
        self.areas[area_id] = area
        self.async_schedule_save()

        self.hass.bus.async_fire_internal(
            EVENT_AREA_REGISTRY_UPDATED,
            EventAreaRegistryUpdatedData(action="create", area_id=area_id),
        )
        return area

    @callback
    def async_delete(self, area_id: str) -> None:
        """Delete area."""
        self.hass.verify_event_loop_thread("area_registry.async_delete")
        device_registry = dr.async_get(self.hass)
        entity_registry = er.async_get(self.hass)
        device_registry.async_clear_area_id(area_id)
        entity_registry.async_clear_area_id(area_id)

        del self.areas[area_id]

        self.hass.bus.async_fire_internal(
            EVENT_AREA_REGISTRY_UPDATED,
            EventAreaRegistryUpdatedData(action="remove", area_id=area_id),
        )

        self.async_schedule_save()

    @callback
    def async_update(
        self,
        area_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        floor_id: str | None | UndefinedType = UNDEFINED,
        humidity_entity_id: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        labels: set[str] | UndefinedType = UNDEFINED,
        motion_entity_id: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
        temperature_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        updated = self._async_update(
            area_id,
            aliases=aliases,
            floor_id=floor_id,
            humidity_entity_id=humidity_entity_id,
            icon=icon,
            labels=labels,
            motion_entity_id=motion_entity_id,
            name=name,
            picture=picture,
            temperature_entity_id=temperature_entity_id,
        )
        # Since updated may be the old or the new and we always fire
        # an event even if nothing has changed we cannot use async_fire_internal
        # here because we do not know if the thread safety check already
        # happened or not in _async_update.
        self.hass.bus.async_fire(
            EVENT_AREA_REGISTRY_UPDATED,
            EventAreaRegistryUpdatedData(action="update", area_id=area_id),
        )
        return updated

    @callback
    def _async_update(
        self,
        area_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        floor_id: str | None | UndefinedType = UNDEFINED,
        humidity_entity_id: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        labels: set[str] | UndefinedType = UNDEFINED,
        motion_entity_id: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
        picture: str | None | UndefinedType = UNDEFINED,
        temperature_entity_id: str | None | UndefinedType = UNDEFINED,
    ) -> AreaEntry:
        """Update name of area."""
        old = self.areas[area_id]

        new_values: dict[str, Any] = {
            attr_name: value
            for attr_name, value in (
                ("aliases", aliases),
                ("floor_id", floor_id),
                ("humidity_entity_id", humidity_entity_id),
                ("icon", icon),
                ("labels", labels),
                ("motion_entity_id", motion_entity_id),
                ("picture", picture),
                ("temperature_entity_id", temperature_entity_id),
            )
            if value is not UNDEFINED and value != getattr(old, attr_name)
        }

        if "humidity_entity_id" in new_values and humidity_entity_id is not None:
            _validate_humidity_entity(self.hass, new_values["humidity_entity_id"])

        if "motion_entity_id" in new_values and motion_entity_id is not None:
            _validate_motion_entity(self.hass, new_values["motion_entity_id"])

        if "temperature_entity_id" in new_values and temperature_entity_id is not None:
            _validate_temperature_entity(self.hass, new_values["temperature_entity_id"])

        if name is not UNDEFINED and name != old.name:
            new_values["name"] = name

        if not new_values:
            return old

        new_values["modified_at"] = utcnow()

        self.hass.verify_event_loop_thread("area_registry.async_update")
        new = self.areas[area_id] = dataclasses.replace(old, **new_values)

        self.async_schedule_save()
        return new

    async def async_load(self) -> None:
        """Load the area registry."""
        self._async_setup_cleanup()

        data = await self._store.async_load()

        areas = AreaRegistryItems()

        if data is not None:
            for area in data["areas"]:
                assert area["name"] is not None and area["id"] is not None
                areas[area["id"]] = AreaEntry(
                    aliases=set(area["aliases"]),
                    floor_id=area["floor_id"],
                    humidity_entity_id=area["humidity_entity_id"],
                    icon=area["icon"],
                    id=area["id"],
                    labels=set(area["labels"]),
                    motion_entity_id=area["motion_entity_id"],
                    name=area["name"],
                    picture=area["picture"],
                    temperature_entity_id=area["temperature_entity_id"],
                    created_at=datetime.fromisoformat(area["created_at"]),
                    modified_at=datetime.fromisoformat(area["modified_at"]),
                )

        self.areas = areas
        self._area_data = areas.data

    @callback
    def _data_to_save(self) -> AreasRegistryStoreData:
        """Return data of area registry to store in a file."""
        return {
            "areas": [
                {
                    "aliases": list(entry.aliases),
                    "floor_id": entry.floor_id,
                    "humidity_entity_id": entry.humidity_entity_id,
                    "icon": entry.icon,
                    "id": entry.id,
                    "labels": list(entry.labels),
                    "motion_entity_id": entry.motion_entity_id,
                    "name": entry.name,
                    "picture": entry.picture,
                    "temperature_entity_id": entry.temperature_entity_id,
                    "created_at": entry.created_at.isoformat(),
                    "modified_at": entry.modified_at.isoformat(),
                }
                for entry in self.areas.values()
            ]
        }

    @callback
    def _async_setup_cleanup(self) -> None:
        """Set up the area registry cleanup."""
        # pylint: disable-next=import-outside-toplevel
        from . import (  # Circular dependencies
            floor_registry as fr,
            label_registry as lr,
        )

        @callback
        def _removed_from_registry_filter(
            event_data: fr.EventFloorRegistryUpdatedData
            | lr.EventLabelRegistryUpdatedData,
        ) -> bool:
            """Filter all except for the item removed from registry events."""
            return event_data["action"] == "remove"

        @callback
        def _handle_floor_registry_update(event: fr.EventFloorRegistryUpdated) -> None:
            """Update areas that are associated with a floor that has been removed."""
            floor_id = event.data["floor_id"]
            for area in self.areas.get_areas_for_floor(floor_id):
                self.async_update(area.id, floor_id=None)

        self.hass.bus.async_listen(
            event_type=fr.EVENT_FLOOR_REGISTRY_UPDATED,
            event_filter=_removed_from_registry_filter,
            listener=_handle_floor_registry_update,
        )

        @callback
        def _handle_label_registry_update(event: lr.EventLabelRegistryUpdated) -> None:
            """Update areas that have a label that has been removed."""
            label_id = event.data["label_id"]
            for area in self.areas.get_areas_for_label(label_id):
                self.async_update(area.id, labels=area.labels - {label_id})

        self.hass.bus.async_listen(
            event_type=lr.EVENT_LABEL_REGISTRY_UPDATED,
            event_filter=_removed_from_registry_filter,
            listener=_handle_label_registry_update,
        )


@callback
@singleton(DATA_REGISTRY)
def async_get(hass: HomeAssistant) -> AreaRegistry:
    """Get area registry."""
    return AreaRegistry(hass)


async def async_load(hass: HomeAssistant) -> None:
    """Load area registry."""
    assert DATA_REGISTRY not in hass.data
    await async_get(hass).async_load()


@callback
def async_entries_for_floor(registry: AreaRegistry, floor_id: str) -> list[AreaEntry]:
    """Return entries that match a floor."""
    return registry.areas.get_areas_for_floor(floor_id)


@callback
def async_entries_for_label(registry: AreaRegistry, label_id: str) -> list[AreaEntry]:
    """Return entries that match a label."""
    return registry.areas.get_areas_for_label(label_id)


def _validate_temperature_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Validate temperature entity."""
    # pylint: disable=import-outside-toplevel
    from homeassistant.components.sensor import SensorDeviceClass

    if not (state := hass.states.get(entity_id)):
        raise ValueError(f"Entity {entity_id} does not exist")

    if (
        state.domain != "sensor"
        or state.attributes.get(ATTR_DEVICE_CLASS) != SensorDeviceClass.TEMPERATURE
    ):
        raise ValueError(f"Entity {entity_id} is not a temperature sensor")


def _validate_humidity_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Validate humidity entity."""
    # pylint: disable=import-outside-toplevel
    from homeassistant.components.sensor import SensorDeviceClass

    if not (state := hass.states.get(entity_id)):
        raise ValueError(f"Entity {entity_id} does not exist")

    if (
        state.domain != "sensor"
        or state.attributes.get(ATTR_DEVICE_CLASS) != SensorDeviceClass.HUMIDITY
    ):
        raise ValueError(f"Entity {entity_id} is not a humidity sensor")


def _validate_motion_entity(hass: HomeAssistant, entity_id: str) -> None:
    """Validate motion entity."""
    # pylint: disable=import-outside-toplevel
    from homeassistant.components.binary_sensor import BinarySensorDeviceClass

    if not (state := hass.states.get(entity_id)):
        raise ValueError(f"Entity {entity_id} does not exist")

    if (
        state.domain != "binary_sensor"
        or state.attributes.get(ATTR_DEVICE_CLASS) != BinarySensorDeviceClass.MOTION
    ):
        raise ValueError(f"Entity {entity_id} is not a motion binary_sensor")
