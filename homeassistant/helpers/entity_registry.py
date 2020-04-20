"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.
"""
import asyncio
from collections import OrderedDict
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, cast

import attr

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, callback, split_entity_id, valid_entity_id
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.loader import bind_hass
from homeassistant.util import slugify
from homeassistant.util.yaml import load_yaml

from .typing import HomeAssistantType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry  # noqa: F401

# mypy: allow-untyped-defs, no-check-untyped-defs

PATH_REGISTRY = "entity_registry.yaml"
DATA_REGISTRY = "entity_registry"
EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)
_UNDEF = object()
DISABLED_CONFIG_ENTRY = "config_entry"
DISABLED_HASS = "hass"
DISABLED_USER = "user"
DISABLED_INTEGRATION = "integration"

ATTR_RESTORED = "restored"

STORAGE_VERSION = 1
STORAGE_KEY = "core.entity_registry"


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id = attr.ib(type=str)
    unique_id = attr.ib(type=str)
    platform = attr.ib(type=str)
    name = attr.ib(type=str, default=None)
    icon = attr.ib(type=str, default=None)
    device_id: Optional[str] = attr.ib(default=None)
    config_entry_id: Optional[str] = attr.ib(default=None)
    disabled_by = attr.ib(
        type=Optional[str],
        default=None,
        validator=attr.validators.in_(
            (
                DISABLED_HASS,
                DISABLED_USER,
                DISABLED_INTEGRATION,
                DISABLED_CONFIG_ENTRY,
                None,
            )
        ),
    )
    capabilities: Optional[Dict[str, Any]] = attr.ib(default=None)
    supported_features: int = attr.ib(default=0)
    device_class: Optional[str] = attr.ib(default=None)
    unit_of_measurement: Optional[str] = attr.ib(default=None)
    # As set by integration
    original_name: Optional[str] = attr.ib(default=None)
    original_icon: Optional[str] = attr.ib(default=None)
    domain = attr.ib(type=str, init=False, repr=False)

    @domain.default
    def _domain_default(self) -> str:
        """Compute domain value."""
        return split_entity_id(self.entity_id)[0]

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None


class EntityRegistry:
    """Class to hold a registry of entities."""

    def __init__(self, hass: HomeAssistantType):
        """Initialize the registry."""
        self.hass = hass
        self.entities: Dict[str, RegistryEntry]
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self.hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, self.async_device_removed
        )

    @callback
    def async_is_registered(self, entity_id: str) -> bool:
        """Check if an entity_id is currently registered."""
        return entity_id in self.entities

    @callback
    def async_get(self, entity_id: str) -> Optional[RegistryEntry]:
        """Get EntityEntry for an entity_id."""
        return self.entities.get(entity_id)

    @callback
    def async_get_entity_id(
        self, domain: str, platform: str, unique_id: str
    ) -> Optional[str]:
        """Check if an entity_id is currently registered."""
        for entity in self.entities.values():
            if (
                entity.domain == domain
                and entity.platform == platform
                and entity.unique_id == unique_id
            ):
                return entity.entity_id
        return None

    @callback
    def async_generate_entity_id(
        self,
        domain: str,
        suggested_object_id: str,
        known_object_ids: Optional[Iterable[str]] = None,
    ) -> str:
        """Generate an entity ID that does not conflict.

        Conflicts checked against registered and currently existing entities.
        """
        preferred_string = f"{domain}.{slugify(suggested_object_id)}"
        test_string = preferred_string
        if not known_object_ids:
            known_object_ids = {}

        tries = 1
        while (
            test_string in self.entities
            or test_string in known_object_ids
            or self.hass.states.get(test_string)
        ):
            tries += 1
            test_string = f"{preferred_string}_{tries}"

        return test_string

    @callback
    def async_get_or_create(
        self,
        domain: str,
        platform: str,
        unique_id: str,
        *,
        # To influence entity ID generation
        suggested_object_id: Optional[str] = None,
        known_object_ids: Optional[Iterable[str]] = None,
        # To disable an entity if it gets created
        disabled_by: Optional[str] = None,
        # Data that we want entry to have
        config_entry: Optional["ConfigEntry"] = None,
        device_id: Optional[str] = None,
        capabilities: Optional[Dict[str, Any]] = None,
        supported_features: Optional[int] = None,
        device_class: Optional[str] = None,
        unit_of_measurement: Optional[str] = None,
        original_name: Optional[str] = None,
        original_icon: Optional[str] = None,
    ) -> RegistryEntry:
        """Get entity. Create if it doesn't exist."""
        config_entry_id = None
        if config_entry:
            config_entry_id = config_entry.entry_id

        entity_id = self.async_get_entity_id(domain, platform, unique_id)

        if entity_id:
            return self._async_update_entity(  # type: ignore
                entity_id,
                config_entry_id=config_entry_id or _UNDEF,
                device_id=device_id or _UNDEF,
                capabilities=capabilities or _UNDEF,
                supported_features=supported_features or _UNDEF,
                device_class=device_class or _UNDEF,
                unit_of_measurement=unit_of_measurement or _UNDEF,
                original_name=original_name or _UNDEF,
                original_icon=original_icon or _UNDEF,
                # When we changed our slugify algorithm, we invalidated some
                # stored entity IDs with either a __ or ending in _.
                # Fix introduced in 0.86 (Jan 23, 2019). Next line can be
                # removed when we release 1.0 or in 2020.
                new_entity_id=".".join(
                    slugify(part) for part in entity_id.split(".", 1)
                ),
            )

        entity_id = self.async_generate_entity_id(
            domain, suggested_object_id or f"{platform}_{unique_id}", known_object_ids
        )

        if (
            disabled_by is None
            and config_entry
            and config_entry.system_options.disable_new_entities
        ):
            disabled_by = DISABLED_INTEGRATION

        entity = RegistryEntry(
            entity_id=entity_id,
            config_entry_id=config_entry_id,
            device_id=device_id,
            unique_id=unique_id,
            platform=platform,
            disabled_by=disabled_by,
            capabilities=capabilities,
            supported_features=supported_features or 0,
            device_class=device_class,
            unit_of_measurement=unit_of_measurement,
            original_name=original_name,
            original_icon=original_icon,
        )
        self.entities[entity_id] = entity
        _LOGGER.info("Registered new %s.%s entity: %s", domain, platform, entity_id)
        self.async_schedule_save()

        self.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
        )

        return entity

    @callback
    def async_remove(self, entity_id: str) -> None:
        """Remove an entity from registry."""
        self.entities.pop(entity_id)
        self.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "remove", "entity_id": entity_id}
        )
        self.async_schedule_save()

    @callback
    def async_device_removed(self, event: Event) -> None:
        """Handle the removal of a device.

        Remove entities from the registry that are associated to a device when
        the device is removed.
        """
        if event.data["action"] != "remove":
            return
        entities = async_entries_for_device(self, event.data["device_id"])
        for entity in entities:
            self.async_remove(entity.entity_id)

    @callback
    def async_update_entity(
        self,
        entity_id,
        *,
        name=_UNDEF,
        icon=_UNDEF,
        new_entity_id=_UNDEF,
        new_unique_id=_UNDEF,
        disabled_by=_UNDEF,
    ):
        """Update properties of an entity."""
        return cast(  # cast until we have _async_update_entity type hinted
            RegistryEntry,
            self._async_update_entity(
                entity_id,
                name=name,
                icon=icon,
                new_entity_id=new_entity_id,
                new_unique_id=new_unique_id,
                disabled_by=disabled_by,
            ),
        )

    @callback
    def _async_update_entity(
        self,
        entity_id,
        *,
        name=_UNDEF,
        icon=_UNDEF,
        config_entry_id=_UNDEF,
        new_entity_id=_UNDEF,
        device_id=_UNDEF,
        new_unique_id=_UNDEF,
        disabled_by=_UNDEF,
        capabilities=_UNDEF,
        supported_features=_UNDEF,
        device_class=_UNDEF,
        unit_of_measurement=_UNDEF,
        original_name=_UNDEF,
        original_icon=_UNDEF,
    ):
        """Private facing update properties method."""
        old = self.entities[entity_id]

        changes = {}

        for attr_name, value in (
            ("name", name),
            ("icon", icon),
            ("config_entry_id", config_entry_id),
            ("device_id", device_id),
            ("disabled_by", disabled_by),
            ("capabilities", capabilities),
            ("supported_features", supported_features),
            ("device_class", device_class),
            ("unit_of_measurement", unit_of_measurement),
            ("original_name", original_name),
            ("original_icon", original_icon),
        ):
            if value is not _UNDEF and value != getattr(old, attr_name):
                changes[attr_name] = value

        if new_entity_id is not _UNDEF and new_entity_id != old.entity_id:
            if self.async_is_registered(new_entity_id):
                raise ValueError("Entity is already registered")

            if not valid_entity_id(new_entity_id):
                raise ValueError("Invalid entity ID")

            if split_entity_id(new_entity_id)[0] != split_entity_id(entity_id)[0]:
                raise ValueError("New entity ID should be same domain")

            self.entities.pop(entity_id)
            entity_id = changes["entity_id"] = new_entity_id

        if new_unique_id is not _UNDEF:
            conflict = next(
                (
                    entity
                    for entity in self.entities.values()
                    if entity.unique_id == new_unique_id
                    and entity.domain == old.domain
                    and entity.platform == old.platform
                ),
                None,
            )
            if conflict:
                raise ValueError(
                    f"Unique id '{new_unique_id}' is already in use by "
                    f"'{conflict.entity_id}'"
                )
            changes["unique_id"] = new_unique_id

        if not changes:
            return old

        new = self.entities[entity_id] = attr.evolve(old, **changes)

        self.async_schedule_save()

        data = {"action": "update", "entity_id": entity_id, "changes": list(changes)}

        if old.entity_id != entity_id:
            data["old_entity_id"] = old.entity_id

        self.hass.bus.async_fire(EVENT_ENTITY_REGISTRY_UPDATED, data)

        return new

    async def async_load(self) -> None:
        """Load the entity registry."""
        async_setup_entity_restore(self.hass, self)

        data = await self.hass.helpers.storage.async_migrator(
            self.hass.config.path(PATH_REGISTRY),
            self._store,
            old_conf_load_func=load_yaml,
            old_conf_migrate_func=_async_migrate,
        )
        entities: Dict[str, RegistryEntry] = OrderedDict()

        if data is not None:
            for entity in data["entities"]:
                entities[entity["entity_id"]] = RegistryEntry(
                    entity_id=entity["entity_id"],
                    config_entry_id=entity.get("config_entry_id"),
                    device_id=entity.get("device_id"),
                    unique_id=entity["unique_id"],
                    platform=entity["platform"],
                    name=entity.get("name"),
                    icon=entity.get("icon"),
                    disabled_by=entity.get("disabled_by"),
                    capabilities=entity.get("capabilities") or {},
                    supported_features=entity.get("supported_features", 0),
                    device_class=entity.get("device_class"),
                    unit_of_measurement=entity.get("unit_of_measurement"),
                    original_name=entity.get("original_name"),
                    original_icon=entity.get("original_icon"),
                )

        self.entities = entities

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the entity registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> Dict[str, Any]:
        """Return data of entity registry to store in a file."""
        data = {}

        data["entities"] = [
            {
                "entity_id": entry.entity_id,
                "config_entry_id": entry.config_entry_id,
                "device_id": entry.device_id,
                "unique_id": entry.unique_id,
                "platform": entry.platform,
                "name": entry.name,
                "icon": entry.icon,
                "disabled_by": entry.disabled_by,
                "capabilities": entry.capabilities,
                "supported_features": entry.supported_features,
                "device_class": entry.device_class,
                "unit_of_measurement": entry.unit_of_measurement,
                "original_name": entry.original_name,
                "original_icon": entry.original_icon,
            }
            for entry in self.entities.values()
        ]

        return data

    @callback
    def async_clear_config_entry(self, config_entry: str) -> None:
        """Clear config entry from registry entries."""
        for entity_id in [
            entity_id
            for entity_id, entry in self.entities.items()
            if config_entry == entry.config_entry_id
        ]:
            self.async_remove(entity_id)


@bind_hass
async def async_get_registry(hass: HomeAssistantType) -> EntityRegistry:
    """Return entity registry instance."""
    reg_or_evt = hass.data.get(DATA_REGISTRY)

    if not reg_or_evt:
        evt = hass.data[DATA_REGISTRY] = asyncio.Event()

        reg = EntityRegistry(hass)
        await reg.async_load()

        hass.data[DATA_REGISTRY] = reg
        evt.set()
        return reg

    if isinstance(reg_or_evt, asyncio.Event):
        evt = reg_or_evt
        await evt.wait()
        return cast(EntityRegistry, hass.data.get(DATA_REGISTRY))

    return cast(EntityRegistry, reg_or_evt)


@callback
def async_entries_for_device(
    registry: EntityRegistry, device_id: str
) -> List[RegistryEntry]:
    """Return entries that match a device."""
    return [
        entry for entry in registry.entities.values() if entry.device_id == device_id
    ]


@callback
def async_entries_for_config_entry(
    registry: EntityRegistry, config_entry_id: str
) -> List[RegistryEntry]:
    """Return entries that match a config entry."""
    return [
        entry
        for entry in registry.entities.values()
        if entry.config_entry_id == config_entry_id
    ]


async def _async_migrate(entities: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Migrate the YAML config file to storage helper format."""
    return {
        "entities": [
            {"entity_id": entity_id, **info} for entity_id, info in entities.items()
        ]
    }


@callback
def async_setup_entity_restore(
    hass: HomeAssistantType, registry: EntityRegistry
) -> None:
    """Set up the entity restore mechanism."""

    @callback
    def cleanup_restored_states(event: Event) -> None:
        """Clean up restored states."""
        if event.data["action"] != "remove":
            return

        state = hass.states.get(event.data["entity_id"])

        if state is None or not state.attributes.get(ATTR_RESTORED):
            return

        hass.states.async_remove(event.data["entity_id"], context=event.context)

    hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, cleanup_restored_states)

    if hass.is_running:
        return

    @callback
    def _write_unavailable_states(_: Event) -> None:
        """Make sure state machine contains entry for each registered entity."""
        states = hass.states
        existing = set(states.async_entity_ids())

        for entry in registry.entities.values():
            if entry.entity_id in existing or entry.disabled:
                continue

            attrs: Dict[str, Any] = {ATTR_RESTORED: True}

            if entry.capabilities is not None:
                attrs.update(entry.capabilities)

            if entry.supported_features is not None:
                attrs[ATTR_SUPPORTED_FEATURES] = entry.supported_features

            if entry.device_class is not None:
                attrs[ATTR_DEVICE_CLASS] = entry.device_class

            if entry.unit_of_measurement is not None:
                attrs[ATTR_UNIT_OF_MEASUREMENT] = entry.unit_of_measurement

            name = entry.name or entry.original_name
            if name is not None:
                attrs[ATTR_FRIENDLY_NAME] = name

            icon = entry.icon or entry.original_icon
            if icon is not None:
                attrs[ATTR_ICON] = icon

            states.async_set(entry.entity_id, STATE_UNAVAILABLE, attrs)

    hass.bus.async_listen(EVENT_HOMEASSISTANT_START, _write_unavailable_states)


async def async_migrate_entries(
    hass: HomeAssistantType,
    config_entry_id: str,
    entry_callback: Callable[[RegistryEntry], Optional[dict]],
) -> None:
    """Migrator of unique IDs."""
    ent_reg = await async_get_registry(hass)

    for entry in ent_reg.entities.values():
        if entry.config_entry_id != config_entry_id:
            continue

        updates = entry_callback(entry)

        if updates is not None:
            ent_reg.async_update_entity(entry.entity_id, **updates)  # type: ignore
