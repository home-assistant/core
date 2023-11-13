"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.
"""
from __future__ import annotations

from collections import UserDict
from collections.abc import Callable, Iterable, Mapping, ValuesView
from datetime import datetime, timedelta
from enum import StrEnum
import logging
import time
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict, TypeVar, cast

import attr
import voluptuous as vol

from homeassistant.backports.functools import cached_property
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_RESTORED,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    MAX_LENGTH_STATE_DOMAIN,
    MAX_LENGTH_STATE_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.exceptions import MaxLengthExceeded
from homeassistant.util import slugify, uuid as uuid_util
from homeassistant.util.json import format_unserializable_data
from homeassistant.util.read_only_dict import ReadOnlyDict

from . import device_registry as dr, storage
from .device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from .json import JSON_DUMP, find_paths_unserializable_data
from .typing import UNDEFINED, UndefinedType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

T = TypeVar("T")

DATA_REGISTRY = "entity_registry"
EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION_MAJOR = 1
STORAGE_VERSION_MINOR = 12
STORAGE_KEY = "core.entity_registry"

CLEANUP_INTERVAL = 3600 * 24
ORPHANED_ENTITY_KEEP_SECONDS = 3600 * 24 * 30

ENTITY_CATEGORY_VALUE_TO_INDEX: dict[EntityCategory | None, int] = {
    # mypy does not understand strenum
    val: idx  # type: ignore[misc]
    for idx, val in enumerate(EntityCategory)
}
ENTITY_CATEGORY_INDEX_TO_VALUE = dict(enumerate(EntityCategory))

# Attributes relevant to describing entity
# to external services.
ENTITY_DESCRIBING_ATTRIBUTES = {
    "capabilities",
    "device_class",
    "entity_id",
    "name",
    "original_name",
    "supported_features",
    "unit_of_measurement",
}


class RegistryEntryDisabler(StrEnum):
    """What disabled a registry entry."""

    CONFIG_ENTRY = "config_entry"
    DEVICE = "device"
    HASS = "hass"
    INTEGRATION = "integration"
    USER = "user"


class RegistryEntryHider(StrEnum):
    """What hid a registry entry."""

    INTEGRATION = "integration"
    USER = "user"


class _EventEntityRegistryUpdatedData_CreateRemove(TypedDict):
    """EventEntityRegistryUpdated data for action type 'create' and 'remove'."""

    action: Literal["create", "remove"]
    entity_id: str


class _EventEntityRegistryUpdatedData_Update(TypedDict):
    """EventEntityRegistryUpdated data for action type 'update'."""

    action: Literal["update"]
    entity_id: str
    changes: dict[str, Any]  # Required with action == "update"
    old_entity_id: NotRequired[str]


EventEntityRegistryUpdatedData = (
    _EventEntityRegistryUpdatedData_CreateRemove
    | _EventEntityRegistryUpdatedData_Update
)


EntityOptionsType = Mapping[str, Mapping[str, Any]]
ReadOnlyEntityOptionsType = ReadOnlyDict[str, ReadOnlyDict[str, Any]]

DISLAY_DICT_OPTIONAL = (
    ("ai", "area_id"),
    ("di", "device_id"),
    ("tk", "translation_key"),
)


def _protect_entity_options(
    data: EntityOptionsType | None,
) -> ReadOnlyEntityOptionsType:
    """Protect entity options from being modified."""
    if data is None:
        return ReadOnlyDict({})
    return ReadOnlyDict({key: ReadOnlyDict(val) for key, val in data.items()})


@attr.s(frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id: str = attr.ib()
    unique_id: str = attr.ib()
    platform: str = attr.ib()
    previous_unique_id: str | None = attr.ib(default=None)
    aliases: set[str] = attr.ib(factory=set)
    area_id: str | None = attr.ib(default=None)
    capabilities: Mapping[str, Any] | None = attr.ib(default=None)
    config_entry_id: str | None = attr.ib(default=None)
    device_class: str | None = attr.ib(default=None)
    device_id: str | None = attr.ib(default=None)
    domain: str = attr.ib(init=False, repr=False)
    disabled_by: RegistryEntryDisabler | None = attr.ib(default=None)
    entity_category: EntityCategory | None = attr.ib(default=None)
    hidden_by: RegistryEntryHider | None = attr.ib(default=None)
    icon: str | None = attr.ib(default=None)
    id: str = attr.ib(
        default=None,
        converter=attr.converters.default_if_none(factory=uuid_util.random_uuid_hex),  # type: ignore[misc]
    )
    has_entity_name: bool = attr.ib(default=False)
    name: str | None = attr.ib(default=None)
    options: ReadOnlyEntityOptionsType = attr.ib(
        default=None, converter=_protect_entity_options
    )
    # As set by integration
    original_device_class: str | None = attr.ib(default=None)
    original_icon: str | None = attr.ib(default=None)
    original_name: str | None = attr.ib(default=None)
    supported_features: int = attr.ib(default=0)
    translation_key: str | None = attr.ib(default=None)
    unit_of_measurement: str | None = attr.ib(default=None)

    @domain.default
    def _domain_default(self) -> str:
        """Compute domain value."""
        return split_entity_id(self.entity_id)[0]

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None

    @property
    def hidden(self) -> bool:
        """Return if entry is hidden."""
        return self.hidden_by is not None

    @property
    def _as_display_dict(self) -> dict[str, Any] | None:
        """Return a partial dict representation of the entry.

        This version only includes what's needed for display.
        Returns None if there's no data needed for display.
        """
        display_dict: dict[str, Any] = {"ei": self.entity_id, "pl": self.platform}
        for key, attr_name in DISLAY_DICT_OPTIONAL:
            if (attr_val := getattr(self, attr_name)) is not None:
                display_dict[key] = attr_val
        if (category := self.entity_category) is not None:
            display_dict["ec"] = ENTITY_CATEGORY_VALUE_TO_INDEX[category]
        if self.hidden_by is not None:
            display_dict["hb"] = True
        if not self.name and self.has_entity_name:
            display_dict["en"] = self.original_name
        if self.domain == "sensor" and (sensor_options := self.options.get("sensor")):
            if (precision := sensor_options.get("display_precision")) is not None:
                display_dict["dp"] = precision
            elif (
                precision := sensor_options.get("suggested_display_precision")
            ) is not None:
                display_dict["dp"] = precision
        return display_dict

    @cached_property
    def display_json_repr(self) -> str | None:
        """Return a cached partial JSON representation of the entry.

        This version only includes what's needed for display.
        """
        try:
            dict_repr = self._as_display_dict
            json_repr: str | None = JSON_DUMP(dict_repr) if dict_repr else None
            return json_repr
        except (ValueError, TypeError):
            _LOGGER.error(
                "Unable to serialize entry %s to JSON. Bad data found at %s",
                self.entity_id,
                format_unserializable_data(
                    find_paths_unserializable_data(dict_repr, dump=JSON_DUMP)
                ),
            )

        return None

    @cached_property
    def as_partial_dict(self) -> dict[str, Any]:
        """Return a partial dict representation of the entry."""
        return {
            "area_id": self.area_id,
            "config_entry_id": self.config_entry_id,
            "device_id": self.device_id,
            "disabled_by": self.disabled_by,
            "entity_category": self.entity_category,
            "entity_id": self.entity_id,
            "has_entity_name": self.has_entity_name,
            "hidden_by": self.hidden_by,
            "icon": self.icon,
            "id": self.id,
            "name": self.name,
            "options": self.options,
            "original_name": self.original_name,
            "platform": self.platform,
            "translation_key": self.translation_key,
            "unique_id": self.unique_id,
        }

    @cached_property
    def extended_dict(self) -> dict[str, Any]:
        """Return a extended dict representation of the entry."""
        return {
            **self.as_partial_dict,
            "aliases": self.aliases,
            "capabilities": self.capabilities,
            "device_class": self.device_class,
            "original_device_class": self.original_device_class,
            "original_icon": self.original_icon,
        }

    @cached_property
    def partial_json_repr(self) -> str | None:
        """Return a cached partial JSON representation of the entry."""
        try:
            dict_repr = self.as_partial_dict
            return JSON_DUMP(dict_repr)
        except (ValueError, TypeError):
            _LOGGER.error(
                "Unable to serialize entry %s to JSON. Bad data found at %s",
                self.entity_id,
                format_unserializable_data(
                    find_paths_unserializable_data(dict_repr, dump=JSON_DUMP)
                ),
            )
        return None

    @callback
    def write_unavailable_state(self, hass: HomeAssistant) -> None:
        """Write the unavailable state to the state machine."""
        attrs: dict[str, Any] = {ATTR_RESTORED: True}

        if self.capabilities is not None:
            attrs.update(self.capabilities)

        device_class = self.device_class or self.original_device_class
        if device_class is not None:
            attrs[ATTR_DEVICE_CLASS] = device_class

        icon = self.icon or self.original_icon
        if icon is not None:
            attrs[ATTR_ICON] = icon

        name = self.name or self.original_name
        if name is not None:
            attrs[ATTR_FRIENDLY_NAME] = name

        if self.supported_features is not None:
            attrs[ATTR_SUPPORTED_FEATURES] = self.supported_features

        if self.unit_of_measurement is not None:
            attrs[ATTR_UNIT_OF_MEASUREMENT] = self.unit_of_measurement

        hass.states.async_set(self.entity_id, STATE_UNAVAILABLE, attrs)


@attr.s(slots=True, frozen=True)
class DeletedRegistryEntry:
    """Deleted Entity Registry Entry."""

    entity_id: str = attr.ib()
    unique_id: str = attr.ib()
    platform: str = attr.ib()
    config_entry_id: str | None = attr.ib()
    domain: str = attr.ib(init=False, repr=False)
    id: str = attr.ib()
    orphaned_timestamp: float | None = attr.ib()

    @domain.default
    def _domain_default(self) -> str:
        """Compute domain value."""
        return split_entity_id(self.entity_id)[0]


class EntityRegistryStore(storage.Store[dict[str, list[dict[str, Any]]]]):
    """Store entity registry data."""

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: dict[str, list[dict[str, Any]]],
    ) -> dict:
        """Migrate to the new version."""
        data = old_data
        if old_major_version == 1 and old_minor_version < 2:
            # Version 1.2 implements migration and freezes the available keys
            for entity in data["entities"]:
                # Populate keys which were introduced before version 1.2
                entity.setdefault("area_id", None)
                entity.setdefault("capabilities", {})
                entity.setdefault("config_entry_id", None)
                entity.setdefault("device_class", None)
                entity.setdefault("device_id", None)
                entity.setdefault("disabled_by", None)
                entity.setdefault("entity_category", None)
                entity.setdefault("icon", None)
                entity.setdefault("name", None)
                entity.setdefault("original_icon", None)
                entity.setdefault("original_name", None)
                entity.setdefault("supported_features", 0)
                entity.setdefault("unit_of_measurement", None)

        if old_major_version == 1 and old_minor_version < 3:
            # Version 1.3 adds original_device_class
            for entity in data["entities"]:
                # Move device_class to original_device_class
                entity["original_device_class"] = entity["device_class"]
                entity["device_class"] = None

        if old_major_version == 1 and old_minor_version < 4:
            # Version 1.4 adds id
            for entity in data["entities"]:
                entity["id"] = uuid_util.random_uuid_hex()

        if old_major_version == 1 and old_minor_version < 5:
            # Version 1.5 adds entity options
            for entity in data["entities"]:
                entity["options"] = {}

        if old_major_version == 1 and old_minor_version < 6:
            # Version 1.6 adds hidden_by
            for entity in data["entities"]:
                entity["hidden_by"] = None

        if old_major_version == 1 and old_minor_version < 7:
            # Version 1.7 adds has_entity_name
            for entity in data["entities"]:
                entity["has_entity_name"] = False

        if old_major_version == 1 and old_minor_version < 8:
            # Cleanup after frontend bug which incorrectly updated device_class
            # Fixed by frontend PR #13551
            for entity in data["entities"]:
                domain = split_entity_id(entity["entity_id"])[0]
                if domain in [Platform.BINARY_SENSOR, Platform.COVER]:
                    continue
                entity["device_class"] = None

        if old_major_version == 1 and old_minor_version < 9:
            # Version 1.9 adds translation_key
            for entity in data["entities"]:
                entity["translation_key"] = None

        if old_major_version == 1 and old_minor_version < 10:
            # Version 1.10 adds aliases
            for entity in data["entities"]:
                entity["aliases"] = []

        if old_major_version == 1 and old_minor_version < 11:
            # Version 1.11 adds deleted_entities
            data["deleted_entities"] = data.get("deleted_entities", [])

        if old_major_version == 1 and old_minor_version < 12:
            # Version 1.12 adds previous_unique_id
            for entity in data["entities"]:
                entity["previous_unique_id"] = None

        if old_major_version > 1:
            raise NotImplementedError
        return data


class EntityRegistryItems(UserDict[str, RegistryEntry]):
    """Container for entity registry items, maps entity_id -> entry.

    Maintains two additional indexes:
    - id -> entry
    - (domain, platform, unique_id) -> entity_id
    """

    def __init__(self) -> None:
        """Initialize the container."""
        super().__init__()
        self._entry_ids: dict[str, RegistryEntry] = {}
        self._index: dict[tuple[str, str, str], str] = {}

    def values(self) -> ValuesView[RegistryEntry]:
        """Return the underlying values to avoid __iter__ overhead."""
        return self.data.values()

    def __setitem__(self, key: str, entry: RegistryEntry) -> None:
        """Add an item."""
        data = self.data
        if key in data:
            old_entry = data[key]
            del self._entry_ids[old_entry.id]
            del self._index[(old_entry.domain, old_entry.platform, old_entry.unique_id)]
        data[key] = entry
        self._entry_ids[entry.id] = entry
        self._index[(entry.domain, entry.platform, entry.unique_id)] = entry.entity_id

    def __delitem__(self, key: str) -> None:
        """Remove an item."""
        entry = self[key]
        del self._entry_ids[entry.id]
        del self._index[(entry.domain, entry.platform, entry.unique_id)]
        super().__delitem__(key)

    def get_entity_id(self, key: tuple[str, str, str]) -> str | None:
        """Get entity_id from (domain, platform, unique_id)."""
        return self._index.get(key)

    def get_entry(self, key: str) -> RegistryEntry | None:
        """Get entry from id."""
        return self._entry_ids.get(key)


class EntityRegistry:
    """Class to hold a registry of entities."""

    deleted_entities: dict[tuple[str, str, str], DeletedRegistryEntry]
    entities: EntityRegistryItems
    _entities_data: dict[str, RegistryEntry]

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the registry."""
        self.hass = hass
        self._store = EntityRegistryStore(
            hass,
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
            minor_version=STORAGE_VERSION_MINOR,
        )
        self.hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, self.async_device_modified
        )

    @callback
    def async_get_device_class_lookup(
        self, domain_device_classes: set[tuple[str, str | None]]
    ) -> dict[str, dict[tuple[str, str | None], str]]:
        """Return a lookup of entity ids for devices which have matching entities.

        Entities must match a set of (domain, device_class) tuples.
        The result is indexed by device_id, then by the matching (domain, device_class)
        """
        lookup: dict[str, dict[tuple[str, str | None], str]] = {}
        for entity in self.entities.values():
            if not entity.device_id:
                continue
            device_class = entity.device_class or entity.original_device_class
            domain_device_class = (entity.domain, device_class)
            if domain_device_class not in domain_device_classes:
                continue
            if entity.device_id not in lookup:
                lookup[entity.device_id] = {domain_device_class: entity.entity_id}
            else:
                lookup[entity.device_id][domain_device_class] = entity.entity_id
        return lookup

    @callback
    def async_is_registered(self, entity_id: str) -> bool:
        """Check if an entity_id is currently registered."""
        return entity_id in self.entities

    @callback
    def async_get(self, entity_id_or_uuid: str) -> RegistryEntry | None:
        """Get EntityEntry for an entity_id or entity entry id.

        We retrieve the RegistryEntry from the underlying dict to avoid
        the overhead of the UserDict __getitem__.
        """
        return self._entities_data.get(entity_id_or_uuid) or self.entities.get_entry(
            entity_id_or_uuid
        )

    @callback
    def async_get_entity_id(
        self, domain: str, platform: str, unique_id: str
    ) -> str | None:
        """Check if an entity_id is currently registered."""
        return self.entities.get_entity_id((domain, platform, unique_id))

    def _entity_id_available(
        self, entity_id: str, known_object_ids: Iterable[str] | None
    ) -> bool:
        """Return True if the entity_id is available.

        An entity_id is available if:
        - It's not registered
        - It's not known by the entity component adding the entity
        - It's not in the state machine

        Note that an entity_id which belongs to a deleted entity is considered
        available.
        """
        if known_object_ids is None:
            known_object_ids = {}

        return (
            entity_id not in self.entities
            and entity_id not in known_object_ids
            and self.hass.states.async_available(entity_id)
        )

    @callback
    def async_generate_entity_id(
        self,
        domain: str,
        suggested_object_id: str,
        known_object_ids: Iterable[str] | None = None,
    ) -> str:
        """Generate an entity ID that does not conflict.

        Conflicts checked against registered and currently existing entities.
        """
        preferred_string = f"{domain}.{slugify(suggested_object_id)}"

        if len(domain) > MAX_LENGTH_STATE_DOMAIN:
            raise MaxLengthExceeded(domain, "domain", MAX_LENGTH_STATE_DOMAIN)

        test_string = preferred_string[:MAX_LENGTH_STATE_ENTITY_ID]
        if known_object_ids is None:
            known_object_ids = {}

        tries = 1
        while not self._entity_id_available(test_string, known_object_ids):
            tries += 1
            len_suffix = len(str(tries)) + 1
            test_string = (
                f"{preferred_string[:MAX_LENGTH_STATE_ENTITY_ID-len_suffix]}_{tries}"
            )

        return test_string

    @callback
    def async_get_or_create(
        self,
        domain: str,
        platform: str,
        unique_id: str,
        *,
        # To influence entity ID generation
        known_object_ids: Iterable[str] | None = None,
        suggested_object_id: str | None = None,
        # To disable or hide an entity if it gets created
        disabled_by: RegistryEntryDisabler | None = None,
        hidden_by: RegistryEntryHider | None = None,
        # Function to generate initial entity options if it gets created
        get_initial_options: Callable[[], EntityOptionsType | None] | None = None,
        # Data that we want entry to have
        capabilities: Mapping[str, Any] | None | UndefinedType = UNDEFINED,
        config_entry: ConfigEntry | None | UndefinedType = UNDEFINED,
        device_id: str | None | UndefinedType = UNDEFINED,
        entity_category: EntityCategory | UndefinedType | None = UNDEFINED,
        has_entity_name: bool | UndefinedType = UNDEFINED,
        original_device_class: str | None | UndefinedType = UNDEFINED,
        original_icon: str | None | UndefinedType = UNDEFINED,
        original_name: str | None | UndefinedType = UNDEFINED,
        supported_features: int | None | UndefinedType = UNDEFINED,
        translation_key: str | None | UndefinedType = UNDEFINED,
        unit_of_measurement: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Get entity. Create if it doesn't exist."""
        config_entry_id: str | None | UndefinedType = UNDEFINED
        if not config_entry:
            config_entry_id = None
        elif config_entry is not UNDEFINED:
            config_entry_id = config_entry.entry_id

        supported_features = supported_features or 0

        entity_id = self.async_get_entity_id(domain, platform, unique_id)

        if entity_id:
            return self.async_update_entity(
                entity_id,
                capabilities=capabilities,
                config_entry_id=config_entry_id,
                device_id=device_id,
                entity_category=entity_category,
                has_entity_name=has_entity_name,
                original_device_class=original_device_class,
                original_icon=original_icon,
                original_name=original_name,
                supported_features=supported_features,
                translation_key=translation_key,
                unit_of_measurement=unit_of_measurement,
            )

        entity_registry_id: str | None = None
        deleted_entity = self.deleted_entities.pop((domain, platform, unique_id), None)
        if deleted_entity is not None:
            # Restore id
            entity_registry_id = deleted_entity.id

        entity_id = self.async_generate_entity_id(
            domain,
            suggested_object_id or f"{platform}_{unique_id}",
            known_object_ids,
        )

        if disabled_by and not isinstance(disabled_by, RegistryEntryDisabler):
            raise ValueError("disabled_by must be a RegistryEntryDisabler value")
        if hidden_by and not isinstance(hidden_by, RegistryEntryHider):
            raise ValueError("hidden_by must be a RegistryEntryHider value")

        if (
            disabled_by is None
            and config_entry
            and config_entry is not UNDEFINED
            and config_entry.pref_disable_new_entities
        ):
            disabled_by = RegistryEntryDisabler.INTEGRATION

        if (
            entity_category
            and entity_category is not UNDEFINED
            and not isinstance(entity_category, EntityCategory)
        ):
            raise ValueError("entity_category must be a valid EntityCategory instance")

        def none_if_undefined(value: T | UndefinedType) -> T | None:
            """Return None if value is UNDEFINED, otherwise return value."""
            return None if value is UNDEFINED else value

        initial_options = get_initial_options() if get_initial_options else None

        entry = RegistryEntry(
            capabilities=none_if_undefined(capabilities),
            config_entry_id=none_if_undefined(config_entry_id),
            device_id=none_if_undefined(device_id),
            disabled_by=disabled_by,
            entity_category=none_if_undefined(entity_category),
            entity_id=entity_id,
            hidden_by=hidden_by,
            has_entity_name=none_if_undefined(has_entity_name) or False,
            id=entity_registry_id,
            options=initial_options,
            original_device_class=none_if_undefined(original_device_class),
            original_icon=none_if_undefined(original_icon),
            original_name=none_if_undefined(original_name),
            platform=platform,
            supported_features=none_if_undefined(supported_features) or 0,
            translation_key=none_if_undefined(translation_key),
            unique_id=unique_id,
            unit_of_measurement=none_if_undefined(unit_of_measurement),
        )
        self.entities[entity_id] = entry
        _LOGGER.info("Registered new %s.%s entity: %s", domain, platform, entity_id)
        self.async_schedule_save()

        self.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
        )

        return entry

    @callback
    def async_remove(self, entity_id: str) -> None:
        """Remove an entity from registry."""
        entity = self.entities.pop(entity_id)
        config_entry_id = entity.config_entry_id
        key = (entity.domain, entity.platform, entity.unique_id)
        # If the entity does not belong to a config entry, mark it as orphaned
        orphaned_timestamp = None if config_entry_id else time.time()
        self.deleted_entities[key] = DeletedRegistryEntry(
            config_entry_id=config_entry_id,
            entity_id=entity_id,
            id=entity.id,
            orphaned_timestamp=orphaned_timestamp,
            platform=entity.platform,
            unique_id=entity.unique_id,
        )
        self.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": entity_id}
        )
        self.async_schedule_save()

    @callback
    def async_device_modified(self, event: Event) -> None:
        """Handle the removal or update of a device.

        Remove entities from the registry that are associated to a device when
        the device is removed.

        Disable entities in the registry that are associated to a device when
        the device is disabled.
        """
        if event.data["action"] == "remove":
            entities = async_entries_for_device(
                self, event.data["device_id"], include_disabled_entities=True
            )
            for entity in entities:
                self.async_remove(entity.entity_id)
            return

        if event.data["action"] != "update":
            # Ignore "create" action
            return

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get(event.data["device_id"])

        # The device may be deleted already if the event handling is late, do nothing
        # in that case. Entities will be removed when we get the "remove" event.
        if not device:
            return

        # Remove entities which belong to config entries no longer associated with the
        # device
        entities = async_entries_for_device(
            self, event.data["device_id"], include_disabled_entities=True
        )
        for entity in entities:
            if (
                entity.config_entry_id is not None
                and entity.config_entry_id not in device.config_entries
            ):
                self.async_remove(entity.entity_id)

        # Re-enable disabled entities if the device is no longer disabled
        if not device.disabled:
            entities = async_entries_for_device(
                self, event.data["device_id"], include_disabled_entities=True
            )
            for entity in entities:
                if entity.disabled_by is not RegistryEntryDisabler.DEVICE:
                    continue
                self.async_update_entity(entity.entity_id, disabled_by=None)
            return

        # Ignore device disabled by config entry, this is handled by
        # async_config_entry_disabled
        if device.disabled_by is dr.DeviceEntryDisabler.CONFIG_ENTRY:
            return

        # Fetch entities which are not already disabled and disable them
        entities = async_entries_for_device(self, event.data["device_id"])
        for entity in entities:
            self.async_update_entity(
                entity.entity_id, disabled_by=RegistryEntryDisabler.DEVICE
            )

    @callback
    def _async_update_entity(
        self,
        entity_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        capabilities: Mapping[str, Any] | None | UndefinedType = UNDEFINED,
        config_entry_id: str | None | UndefinedType = UNDEFINED,
        device_class: str | None | UndefinedType = UNDEFINED,
        device_id: str | None | UndefinedType = UNDEFINED,
        disabled_by: RegistryEntryDisabler | None | UndefinedType = UNDEFINED,
        entity_category: EntityCategory | None | UndefinedType = UNDEFINED,
        hidden_by: RegistryEntryHider | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        has_entity_name: bool | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        new_entity_id: str | UndefinedType = UNDEFINED,
        new_unique_id: str | UndefinedType = UNDEFINED,
        options: EntityOptionsType | UndefinedType = UNDEFINED,
        original_device_class: str | None | UndefinedType = UNDEFINED,
        original_icon: str | None | UndefinedType = UNDEFINED,
        original_name: str | None | UndefinedType = UNDEFINED,
        platform: str | None | UndefinedType = UNDEFINED,
        supported_features: int | UndefinedType = UNDEFINED,
        translation_key: str | None | UndefinedType = UNDEFINED,
        unit_of_measurement: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Private facing update properties method."""
        old = self.entities[entity_id]

        new_values: dict[str, Any] = {}  # Dict with new key/value pairs
        old_values: dict[str, Any] = {}  # Dict with old key/value pairs

        if (
            disabled_by
            and disabled_by is not UNDEFINED
            and not isinstance(disabled_by, RegistryEntryDisabler)
        ):
            raise ValueError("disabled_by must be a RegistryEntryDisabler value")
        if (
            hidden_by
            and hidden_by is not UNDEFINED
            and not isinstance(hidden_by, RegistryEntryHider)
        ):
            raise ValueError("hidden_by must be a RegistryEntryHider value")

        if (
            entity_category
            and entity_category is not UNDEFINED
            and not isinstance(entity_category, EntityCategory)
        ):
            raise ValueError("entity_category must be a valid EntityCategory instance")

        for attr_name, value in (
            ("aliases", aliases),
            ("area_id", area_id),
            ("capabilities", capabilities),
            ("config_entry_id", config_entry_id),
            ("device_class", device_class),
            ("device_id", device_id),
            ("disabled_by", disabled_by),
            ("entity_category", entity_category),
            ("hidden_by", hidden_by),
            ("icon", icon),
            ("has_entity_name", has_entity_name),
            ("name", name),
            ("options", options),
            ("original_device_class", original_device_class),
            ("original_icon", original_icon),
            ("original_name", original_name),
            ("platform", platform),
            ("supported_features", supported_features),
            ("translation_key", translation_key),
            ("unit_of_measurement", unit_of_measurement),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value
                old_values[attr_name] = getattr(old, attr_name)

        if new_entity_id is not UNDEFINED and new_entity_id != old.entity_id:
            if not self._entity_id_available(new_entity_id, None):
                raise ValueError("Entity with this ID is already registered")

            if not valid_entity_id(new_entity_id):
                raise ValueError("Invalid entity ID")

            if split_entity_id(new_entity_id)[0] != split_entity_id(entity_id)[0]:
                raise ValueError("New entity ID should be same domain")

            self.entities.pop(entity_id)
            entity_id = new_values["entity_id"] = new_entity_id
            old_values["entity_id"] = old.entity_id

        if new_unique_id is not UNDEFINED:
            conflict_entity_id = self.async_get_entity_id(
                old.domain, old.platform, new_unique_id
            )
            if conflict_entity_id:
                raise ValueError(
                    f"Unique id '{new_unique_id}' is already in use by "
                    f"'{conflict_entity_id}'"
                )
            new_values["unique_id"] = new_unique_id
            old_values["unique_id"] = old.unique_id
            new_values["previous_unique_id"] = old.unique_id

        if not new_values:
            return old

        new = self.entities[entity_id] = attr.evolve(old, **new_values)

        self.async_schedule_save()

        data: dict[str, str | dict[str, Any]] = {
            "action": "update",
            "entity_id": entity_id,
            "changes": old_values,
        }

        if old.entity_id != entity_id:
            data["old_entity_id"] = old.entity_id

        self.hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, data)

        return new

    @callback
    def async_update_entity(
        self,
        entity_id: str,
        *,
        aliases: set[str] | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        capabilities: Mapping[str, Any] | None | UndefinedType = UNDEFINED,
        config_entry_id: str | None | UndefinedType = UNDEFINED,
        device_class: str | None | UndefinedType = UNDEFINED,
        device_id: str | None | UndefinedType = UNDEFINED,
        disabled_by: RegistryEntryDisabler | None | UndefinedType = UNDEFINED,
        entity_category: EntityCategory | None | UndefinedType = UNDEFINED,
        hidden_by: RegistryEntryHider | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        has_entity_name: bool | UndefinedType = UNDEFINED,
        name: str | None | UndefinedType = UNDEFINED,
        new_entity_id: str | UndefinedType = UNDEFINED,
        new_unique_id: str | UndefinedType = UNDEFINED,
        original_device_class: str | None | UndefinedType = UNDEFINED,
        original_icon: str | None | UndefinedType = UNDEFINED,
        original_name: str | None | UndefinedType = UNDEFINED,
        supported_features: int | UndefinedType = UNDEFINED,
        translation_key: str | None | UndefinedType = UNDEFINED,
        unit_of_measurement: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Update properties of an entity."""
        return self._async_update_entity(
            entity_id,
            aliases=aliases,
            area_id=area_id,
            capabilities=capabilities,
            config_entry_id=config_entry_id,
            device_class=device_class,
            device_id=device_id,
            disabled_by=disabled_by,
            entity_category=entity_category,
            hidden_by=hidden_by,
            icon=icon,
            has_entity_name=has_entity_name,
            name=name,
            new_entity_id=new_entity_id,
            new_unique_id=new_unique_id,
            original_device_class=original_device_class,
            original_icon=original_icon,
            original_name=original_name,
            supported_features=supported_features,
            translation_key=translation_key,
            unit_of_measurement=unit_of_measurement,
        )

    @callback
    def async_update_entity_platform(
        self,
        entity_id: str,
        new_platform: str,
        *,
        new_config_entry_id: str | UndefinedType = UNDEFINED,
        new_unique_id: str | UndefinedType = UNDEFINED,
        new_device_id: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Update entity platform.

        This should only be used when an entity needs to be migrated between
        integrations.
        """
        if (
            state := self.hass.states.get(entity_id)
        ) is not None and state.state != STATE_UNKNOWN:
            raise ValueError("Only entities that haven't been loaded can be migrated")

        old = self.entities[entity_id]
        if new_config_entry_id == UNDEFINED and old.config_entry_id is not None:
            raise ValueError(
                f"new_config_entry_id required because {entity_id} is already linked "
                "to a config entry"
            )

        return self._async_update_entity(
            entity_id,
            new_unique_id=new_unique_id,
            config_entry_id=new_config_entry_id,
            device_id=new_device_id,
            platform=new_platform,
        )

    @callback
    def async_update_entity_options(
        self, entity_id: str, domain: str, options: Mapping[str, Any] | None
    ) -> RegistryEntry:
        """Update entity options for a domain.

        If the domain options are set to None, they will be removed.
        """
        old = self.entities[entity_id]
        new_options: dict[str, Mapping] = {
            key: value for key, value in old.options.items() if key != domain
        }
        if options is not None:
            new_options[domain] = options
        return self._async_update_entity(entity_id, options=new_options)

    async def async_load(self) -> None:
        """Load the entity registry."""
        _async_setup_cleanup(self.hass, self)
        _async_setup_entity_restore(self.hass, self)

        data = await self._store.async_load()
        entities = EntityRegistryItems()
        deleted_entities: dict[tuple[str, str, str], DeletedRegistryEntry] = {}

        if data is not None:
            for entity in data["entities"]:
                # We removed this in 2022.5. Remove this check in 2023.1.
                if entity["entity_category"] == "system":
                    entity["entity_category"] = None

                entities[entity["entity_id"]] = RegistryEntry(
                    aliases=set(entity["aliases"]),
                    area_id=entity["area_id"],
                    capabilities=entity["capabilities"],
                    config_entry_id=entity["config_entry_id"],
                    device_class=entity["device_class"],
                    device_id=entity["device_id"],
                    disabled_by=RegistryEntryDisabler(entity["disabled_by"])
                    if entity["disabled_by"]
                    else None,
                    entity_category=EntityCategory(entity["entity_category"])
                    if entity["entity_category"]
                    else None,
                    entity_id=entity["entity_id"],
                    hidden_by=RegistryEntryHider(entity["hidden_by"])
                    if entity["hidden_by"]
                    else None,
                    icon=entity["icon"],
                    id=entity["id"],
                    has_entity_name=entity["has_entity_name"],
                    name=entity["name"],
                    options=entity["options"],
                    original_device_class=entity["original_device_class"],
                    original_icon=entity["original_icon"],
                    original_name=entity["original_name"],
                    platform=entity["platform"],
                    supported_features=entity["supported_features"],
                    translation_key=entity["translation_key"],
                    unique_id=entity["unique_id"],
                    previous_unique_id=entity["previous_unique_id"],
                    unit_of_measurement=entity["unit_of_measurement"],
                )
            for entity in data["deleted_entities"]:
                key = (
                    split_entity_id(entity["entity_id"])[0],
                    entity["platform"],
                    entity["unique_id"],
                )
                deleted_entities[key] = DeletedRegistryEntry(
                    config_entry_id=entity["config_entry_id"],
                    entity_id=entity["entity_id"],
                    id=entity["id"],
                    orphaned_timestamp=entity["orphaned_timestamp"],
                    platform=entity["platform"],
                    unique_id=entity["unique_id"],
                )

        self.deleted_entities = deleted_entities
        self.entities = entities
        self._entities_data = entities.data

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the entity registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of entity registry to store in a file."""
        data: dict[str, Any] = {}

        data["entities"] = [
            {
                "aliases": list(entry.aliases),
                "area_id": entry.area_id,
                "capabilities": entry.capabilities,
                "config_entry_id": entry.config_entry_id,
                "device_class": entry.device_class,
                "device_id": entry.device_id,
                "disabled_by": entry.disabled_by,
                "entity_category": entry.entity_category,
                "entity_id": entry.entity_id,
                "hidden_by": entry.hidden_by,
                "icon": entry.icon,
                "id": entry.id,
                "has_entity_name": entry.has_entity_name,
                "name": entry.name,
                "options": entry.options,
                "original_device_class": entry.original_device_class,
                "original_icon": entry.original_icon,
                "original_name": entry.original_name,
                "platform": entry.platform,
                "supported_features": entry.supported_features,
                "translation_key": entry.translation_key,
                "unique_id": entry.unique_id,
                "previous_unique_id": entry.previous_unique_id,
                "unit_of_measurement": entry.unit_of_measurement,
            }
            for entry in self.entities.values()
        ]
        data["deleted_entities"] = [
            {
                "config_entry_id": entry.config_entry_id,
                "entity_id": entry.entity_id,
                "id": entry.id,
                "orphaned_timestamp": entry.orphaned_timestamp,
                "platform": entry.platform,
                "unique_id": entry.unique_id,
            }
            for entry in self.deleted_entities.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry_id: str) -> None:
        """Clear config entry from registry entries."""
        now_time = time.time()
        for entity_id in [
            entity_id
            for entity_id, entry in self.entities.items()
            if config_entry_id == entry.config_entry_id
        ]:
            self.async_remove(entity_id)
        for key, deleted_entity in list(self.deleted_entities.items()):
            if config_entry_id != deleted_entity.config_entry_id:
                continue
            # Add a time stamp when the deleted entity became orphaned
            self.deleted_entities[key] = attr.evolve(
                deleted_entity, orphaned_timestamp=now_time, config_entry_id=None
            )
            self.async_schedule_save()

    @callback
    def async_purge_expired_orphaned_entities(self) -> None:
        """Purge expired orphaned entities from the registry.

        We need to purge these periodically to avoid the database
        growing without bound.
        """
        now_time = time.time()
        for key, deleted_entity in list(self.deleted_entities.items()):
            if (orphaned_timestamp := deleted_entity.orphaned_timestamp) is None:
                continue

            if orphaned_timestamp + ORPHANED_ENTITY_KEEP_SECONDS < now_time:
                self.deleted_entities.pop(key)
                self.async_schedule_save()

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for entity_id, entry in self.entities.items():
            if area_id == entry.area_id:
                self.async_update_entity(entity_id, area_id=None)


@callback
def async_get(hass: HomeAssistant) -> EntityRegistry:
    """Get entity registry."""
    return cast(EntityRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load entity registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = EntityRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@callback
def async_entries_for_device(
    registry: EntityRegistry, device_id: str, include_disabled_entities: bool = False
) -> list[RegistryEntry]:
    """Return entries that match a device."""
    return [
        entry
        for entry in registry.entities.values()
        if entry.device_id == device_id
        and (not entry.disabled_by or include_disabled_entities)
    ]


@callback
def async_entries_for_area(
    registry: EntityRegistry, area_id: str
) -> list[RegistryEntry]:
    """Return entries that match an area."""
    return [entry for entry in registry.entities.values() if entry.area_id == area_id]


@callback
def async_entries_for_config_entry(
    registry: EntityRegistry, config_entry_id: str
) -> list[RegistryEntry]:
    """Return entries that match a config entry."""
    return [
        entry
        for entry in registry.entities.values()
        if entry.config_entry_id == config_entry_id
    ]


@callback
def async_config_entry_disabled_by_changed(
    registry: EntityRegistry, config_entry: ConfigEntry
) -> None:
    """Handle a config entry being disabled or enabled.

    Disable entities in the registry that are associated with a config entry when
    the config entry is disabled, enable entities in the registry that are associated
    with a config entry when the config entry is enabled and the entities are marked
    DISABLED_CONFIG_ENTRY.
    """

    entities = async_entries_for_config_entry(registry, config_entry.entry_id)

    if not config_entry.disabled_by:
        for entity in entities:
            if entity.disabled_by is not RegistryEntryDisabler.CONFIG_ENTRY:
                continue
            registry.async_update_entity(entity.entity_id, disabled_by=None)
        return

    for entity in entities:
        if entity.disabled:
            # Entity already disabled, do not overwrite
            continue
        registry.async_update_entity(
            entity.entity_id, disabled_by=RegistryEntryDisabler.CONFIG_ENTRY
        )


@callback
def _async_setup_cleanup(hass: HomeAssistant, registry: EntityRegistry) -> None:
    """Clean up device registry when entities removed."""
    from . import event  # pylint: disable=import-outside-toplevel

    @callback
    def cleanup(_: datetime) -> None:
        """Clean up entity registry."""
        # Periodic purge of orphaned entities to avoid the registry
        # growing without bounds when there are lots of deleted entities
        registry.async_purge_expired_orphaned_entities()

    cancel = event.async_track_time_interval(
        hass, cleanup, timedelta(seconds=CLEANUP_INTERVAL)
    )

    @callback
    def _on_homeassistant_stop(event: Event) -> None:
        """Cancel cleanup."""
        cancel()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _on_homeassistant_stop)


@callback
def _async_setup_entity_restore(hass: HomeAssistant, registry: EntityRegistry) -> None:
    """Set up the entity restore mechanism."""

    @callback
    def cleanup_restored_states_filter(event: Event) -> bool:
        """Clean up restored states filter."""
        return bool(event.data["action"] == "remove")

    @callback
    def cleanup_restored_states(event: Event) -> None:
        """Clean up restored states."""
        state = hass.states.get(event.data["entity_id"])

        if state is None or not state.attributes.get(ATTR_RESTORED):
            return

        hass.states.async_remove(event.data["entity_id"], context=event.context)

    hass.bus.async_listen(
        EVENT_ENTITY_REGISTRY_UPDATED,
        cleanup_restored_states,
        event_filter=cleanup_restored_states_filter,
    )

    if hass.is_running:
        return

    @callback
    def _write_unavailable_states(_: Event) -> None:
        """Make sure state machine contains entry for each registered entity."""
        existing = set(hass.states.async_entity_ids())

        for entry in registry.entities.values():
            if entry.entity_id in existing or entry.disabled:
                continue

            entry.write_unavailable_state(hass)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, _write_unavailable_states)


async def async_migrate_entries(
    hass: HomeAssistant,
    config_entry_id: str,
    entry_callback: Callable[[RegistryEntry], dict[str, Any] | None],
) -> None:
    """Migrate entity registry entries which belong to a config entry.

    Can be used as a migrator of unique_ids or to update other entity registry data.
    Can also be used to remove duplicated entity registry entries.
    """
    ent_reg = async_get(hass)

    for entry in list(ent_reg.entities.values()):
        if entry.config_entry_id != config_entry_id:
            continue
        if not ent_reg.entities.get_entry(entry.id):
            continue

        updates = entry_callback(entry)

        if updates is not None:
            ent_reg.async_update_entity(entry.entity_id, **updates)


@callback
def async_validate_entity_id(registry: EntityRegistry, entity_id_or_uuid: str) -> str:
    """Validate and resolve an entity id or UUID to an entity id.

    Raises vol.Invalid if the entity or UUID is invalid, or if the UUID is not
    associated with an entity registry item.
    """
    if valid_entity_id(entity_id_or_uuid):
        return entity_id_or_uuid
    if (entry := registry.entities.get_entry(entity_id_or_uuid)) is None:
        raise vol.Invalid(f"Unknown entity registry entry {entity_id_or_uuid}")
    return entry.entity_id


@callback
def async_resolve_entity_id(
    registry: EntityRegistry, entity_id_or_uuid: str
) -> str | None:
    """Validate and resolve an entity id or UUID to an entity id.

    Returns None if the entity or UUID is invalid, or if the UUID is not
    associated with an entity registry item.
    """
    if valid_entity_id(entity_id_or_uuid):
        return entity_id_or_uuid
    if (entry := registry.entities.get_entry(entity_id_or_uuid)) is None:
        return None
    return entry.entity_id


@callback
def async_validate_entity_ids(
    registry: EntityRegistry, entity_ids_or_uuids: list[str]
) -> list[str]:
    """Validate and resolve a list of entity ids or UUIDs to a list of entity ids.

    Returns a list with UUID resolved to entity_ids.
    Raises vol.Invalid if any item is invalid, or if any a UUID is not associated with
    an entity registry item.
    """

    return [async_validate_entity_id(registry, item) for item in entity_ids_or_uuids]
