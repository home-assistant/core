"""Provide a registry to track entity IDs.

The Entity Registry keeps a registry of entities. Entities are uniquely
identified by their domain, platform and a unique id provided by that platform.

The Entity Registry will persist itself 10 seconds after a new entity is
registered. Registering a new entity while a timer is in progress resets the
timer.
"""
from __future__ import annotations

from collections import OrderedDict
import logging
from typing import TYPE_CHECKING, Any, Callable, Iterable, cast

import attr

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_RESTORED,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    EVENT_HOMEASSISTANT_START,
    STATE_UNAVAILABLE,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    callback,
    split_entity_id,
    valid_entity_id,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import EVENT_DEVICE_REGISTRY_UPDATED
from homeassistant.loader import bind_hass
from homeassistant.util import slugify
from homeassistant.util.yaml import load_yaml

from .typing import UNDEFINED, UndefinedType

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

PATH_REGISTRY = "entity_registry.yaml"
DATA_REGISTRY = "entity_registry"
EVENT_ENTITY_REGISTRY_UPDATED = "entity_registry_updated"
SAVE_DELAY = 10
_LOGGER = logging.getLogger(__name__)
DISABLED_CONFIG_ENTRY = "config_entry"
DISABLED_DEVICE = "device"
DISABLED_HASS = "hass"
DISABLED_INTEGRATION = "integration"
DISABLED_USER = "user"

STORAGE_VERSION = 1
STORAGE_KEY = "core.entity_registry"

# Attributes relevant to describing entity
# to external services.
ENTITY_DESCRIBING_ATTRIBUTES = {
    "entity_id",
    "name",
    "original_name",
    "capabilities",
    "supported_features",
    "device_class",
    "unit_of_measurement",
}


@attr.s(slots=True, frozen=True)
class RegistryEntry:
    """Entity Registry Entry."""

    entity_id: str = attr.ib()
    unique_id: str = attr.ib()
    platform: str = attr.ib()
    name: str | None = attr.ib(default=None)
    icon: str | None = attr.ib(default=None)
    device_id: str | None = attr.ib(default=None)
    area_id: str | None = attr.ib(default=None)
    config_entry_id: str | None = attr.ib(default=None)
    disabled_by: str | None = attr.ib(
        default=None,
        validator=attr.validators.in_(
            (
                DISABLED_CONFIG_ENTRY,
                DISABLED_DEVICE,
                DISABLED_HASS,
                DISABLED_INTEGRATION,
                DISABLED_USER,
                None,
            )
        ),
    )
    capabilities: dict[str, Any] | None = attr.ib(default=None)
    supported_features: int = attr.ib(default=0)
    device_class: str | None = attr.ib(default=None)
    unit_of_measurement: str | None = attr.ib(default=None)
    # As set by integration
    original_name: str | None = attr.ib(default=None)
    original_icon: str | None = attr.ib(default=None)
    domain: str = attr.ib(init=False, repr=False)

    @domain.default
    def _domain_default(self) -> str:
        """Compute domain value."""
        return split_entity_id(self.entity_id)[0]

    @property
    def disabled(self) -> bool:
        """Return if entry is disabled."""
        return self.disabled_by is not None

    @callback
    def write_unavailable_state(self, hass: HomeAssistant) -> None:
        """Write the unavailable state to the state machine."""
        attrs: dict[str, Any] = {ATTR_RESTORED: True}

        if self.capabilities is not None:
            attrs.update(self.capabilities)

        if self.supported_features is not None:
            attrs[ATTR_SUPPORTED_FEATURES] = self.supported_features

        if self.device_class is not None:
            attrs[ATTR_DEVICE_CLASS] = self.device_class

        if self.unit_of_measurement is not None:
            attrs[ATTR_UNIT_OF_MEASUREMENT] = self.unit_of_measurement

        name = self.name or self.original_name
        if name is not None:
            attrs[ATTR_FRIENDLY_NAME] = name

        icon = self.icon or self.original_icon
        if icon is not None:
            attrs[ATTR_ICON] = icon

        hass.states.async_set(self.entity_id, STATE_UNAVAILABLE, attrs)


class EntityRegistry:
    """Class to hold a registry of entities."""

    def __init__(self, hass: HomeAssistant):
        """Initialize the registry."""
        self.hass = hass
        self.entities: dict[str, RegistryEntry]
        self._index: dict[tuple[str, str, str], str] = {}
        self._store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
        self.hass.bus.async_listen(
            EVENT_DEVICE_REGISTRY_UPDATED, self.async_device_modified
        )

    @callback
    def async_get_device_class_lookup(self, domain_device_classes: set) -> dict:
        """Return a lookup for the device class by domain."""
        lookup: dict[str, dict[tuple[Any, Any], str]] = {}
        for entity in self.entities.values():
            if not entity.device_id:
                continue
            domain_device_class = (entity.domain, entity.device_class)
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
    def async_get(self, entity_id: str) -> RegistryEntry | None:
        """Get EntityEntry for an entity_id."""
        return self.entities.get(entity_id)

    @callback
    def async_get_entity_id(
        self, domain: str, platform: str, unique_id: str
    ) -> str | None:
        """Check if an entity_id is currently registered."""
        return self._index.get((domain, platform, unique_id))

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
        test_string = preferred_string
        if not known_object_ids:
            known_object_ids = {}

        tries = 1
        while (
            test_string in self.entities
            or test_string in known_object_ids
            or not self.hass.states.async_available(test_string)
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
        suggested_object_id: str | None = None,
        known_object_ids: Iterable[str] | None = None,
        # To disable an entity if it gets created
        disabled_by: str | None = None,
        # Data that we want entry to have
        config_entry: ConfigEntry | None = None,
        device_id: str | None = None,
        area_id: str | None = None,
        capabilities: dict[str, Any] | None = None,
        supported_features: int | None = None,
        device_class: str | None = None,
        unit_of_measurement: str | None = None,
        original_name: str | None = None,
        original_icon: str | None = None,
    ) -> RegistryEntry:
        """Get entity. Create if it doesn't exist."""
        config_entry_id = None
        if config_entry:
            config_entry_id = config_entry.entry_id

        entity_id = self.async_get_entity_id(domain, platform, unique_id)

        if entity_id:
            return self._async_update_entity(
                entity_id,
                config_entry_id=config_entry_id or UNDEFINED,
                device_id=device_id or UNDEFINED,
                area_id=area_id or UNDEFINED,
                capabilities=capabilities or UNDEFINED,
                supported_features=supported_features or UNDEFINED,
                device_class=device_class or UNDEFINED,
                unit_of_measurement=unit_of_measurement or UNDEFINED,
                original_name=original_name or UNDEFINED,
                original_icon=original_icon or UNDEFINED,
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
            area_id=area_id,
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
        self._register_entry(entity)
        _LOGGER.info("Registered new %s.%s entity: %s", domain, platform, entity_id)
        self.async_schedule_save()

        self.hass.bus.async_fire(
            EVENT_ENTITY_REGISTRY_UPDATED, {"action": "create", "entity_id": entity_id}
        )

        return entity

    @callback
    def async_remove(self, entity_id: str) -> None:
        """Remove an entity from registry."""
        self._unregister_entry(self.entities[entity_id])
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
            return

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get(event.data["device_id"])

        # The device may be deleted already if the event handling is late
        if not device or not device.disabled:
            entities = async_entries_for_device(
                self, event.data["device_id"], include_disabled_entities=True
            )
            for entity in entities:
                if entity.disabled_by != DISABLED_DEVICE:
                    continue
                self.async_update_entity(entity.entity_id, disabled_by=None)
            return

        if device.disabled_by == dr.DISABLED_CONFIG_ENTRY:
            # Handled by async_config_entry_disabled
            return

        # Fetch entities which are not already disabled
        entities = async_entries_for_device(self, event.data["device_id"])
        for entity in entities:
            self.async_update_entity(entity.entity_id, disabled_by=DISABLED_DEVICE)

    @callback
    def async_update_entity(
        self,
        entity_id: str,
        *,
        name: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        new_entity_id: str | UndefinedType = UNDEFINED,
        new_unique_id: str | UndefinedType = UNDEFINED,
        disabled_by: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Update properties of an entity."""
        return self._async_update_entity(
            entity_id,
            name=name,
            icon=icon,
            area_id=area_id,
            new_entity_id=new_entity_id,
            new_unique_id=new_unique_id,
            disabled_by=disabled_by,
        )

    @callback
    def _async_update_entity(
        self,
        entity_id: str,
        *,
        name: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        config_entry_id: str | None | UndefinedType = UNDEFINED,
        new_entity_id: str | UndefinedType = UNDEFINED,
        device_id: str | None | UndefinedType = UNDEFINED,
        area_id: str | None | UndefinedType = UNDEFINED,
        new_unique_id: str | UndefinedType = UNDEFINED,
        disabled_by: str | None | UndefinedType = UNDEFINED,
        capabilities: dict[str, Any] | None | UndefinedType = UNDEFINED,
        supported_features: int | UndefinedType = UNDEFINED,
        device_class: str | None | UndefinedType = UNDEFINED,
        unit_of_measurement: str | None | UndefinedType = UNDEFINED,
        original_name: str | None | UndefinedType = UNDEFINED,
        original_icon: str | None | UndefinedType = UNDEFINED,
    ) -> RegistryEntry:
        """Private facing update properties method."""
        old = self.entities[entity_id]

        new_values = {}  # Dict with new key/value pairs
        old_values = {}  # Dict with old key/value pairs

        for attr_name, value in (
            ("name", name),
            ("icon", icon),
            ("config_entry_id", config_entry_id),
            ("device_id", device_id),
            ("area_id", area_id),
            ("disabled_by", disabled_by),
            ("capabilities", capabilities),
            ("supported_features", supported_features),
            ("device_class", device_class),
            ("unit_of_measurement", unit_of_measurement),
            ("original_name", original_name),
            ("original_icon", original_icon),
        ):
            if value is not UNDEFINED and value != getattr(old, attr_name):
                new_values[attr_name] = value
                old_values[attr_name] = getattr(old, attr_name)

        if new_entity_id is not UNDEFINED and new_entity_id != old.entity_id:
            if self.async_is_registered(new_entity_id):
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

        if not new_values:
            return old

        self._remove_index(old)
        new = attr.evolve(old, **new_values)
        self._register_entry(new)

        self.async_schedule_save()

        data = {"action": "update", "entity_id": entity_id, "changes": old_values}

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
        entities: dict[str, RegistryEntry] = OrderedDict()

        if data is not None:
            for entity in data["entities"]:
                # Some old installations can have some bad entities.
                # Filter them out as they cause errors down the line.
                # Can be removed in Jan 2021
                if not valid_entity_id(entity["entity_id"]):
                    continue

                entities[entity["entity_id"]] = RegistryEntry(
                    entity_id=entity["entity_id"],
                    config_entry_id=entity.get("config_entry_id"),
                    device_id=entity.get("device_id"),
                    area_id=entity.get("area_id"),
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
        self._rebuild_index()

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the entity registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, Any]:
        """Return data of entity registry to store in a file."""
        data = {}

        data["entities"] = [
            {
                "entity_id": entry.entity_id,
                "config_entry_id": entry.config_entry_id,
                "device_id": entry.device_id,
                "area_id": entry.area_id,
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

    @callback
    def async_clear_area_id(self, area_id: str) -> None:
        """Clear area id from registry entries."""
        for entity_id, entry in self.entities.items():
            if area_id == entry.area_id:
                self._async_update_entity(entity_id, area_id=None)

    def _register_entry(self, entry: RegistryEntry) -> None:
        self.entities[entry.entity_id] = entry
        self._add_index(entry)

    def _add_index(self, entry: RegistryEntry) -> None:
        self._index[(entry.domain, entry.platform, entry.unique_id)] = entry.entity_id

    def _unregister_entry(self, entry: RegistryEntry) -> None:
        self._remove_index(entry)
        del self.entities[entry.entity_id]

    def _remove_index(self, entry: RegistryEntry) -> None:
        del self._index[(entry.domain, entry.platform, entry.unique_id)]

    def _rebuild_index(self) -> None:
        self._index = {}
        for entry in self.entities.values():
            self._add_index(entry)


@callback
def async_get(hass: HomeAssistant) -> EntityRegistry:
    """Get entity registry."""
    return cast(EntityRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load entity registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = EntityRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


@bind_hass
async def async_get_registry(hass: HomeAssistant) -> EntityRegistry:
    """Get entity registry.

    This is deprecated and will be removed in the future. Use async_get instead.
    """
    return async_get(hass)


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
            if entity.disabled_by != DISABLED_CONFIG_ENTRY:
                continue
            registry.async_update_entity(entity.entity_id, disabled_by=None)
        return

    for entity in entities:
        if entity.disabled:
            # Entity already disabled, do not overwrite
            continue
        registry.async_update_entity(
            entity.entity_id, disabled_by=DISABLED_CONFIG_ENTRY
        )


async def _async_migrate(entities: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Migrate the YAML config file to storage helper format."""
    return {
        "entities": [
            {"entity_id": entity_id, **info} for entity_id, info in entities.items()
        ]
    }


@callback
def async_setup_entity_restore(hass: HomeAssistant, registry: EntityRegistry) -> None:
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
    entry_callback: Callable[[RegistryEntry], dict | None],
) -> None:
    """Migrator of unique IDs."""
    ent_reg = await async_get_registry(hass)

    for entry in ent_reg.entities.values():
        if entry.config_entry_id != config_entry_id:
            continue

        updates = entry_callback(entry)

        if updates is not None:
            ent_reg.async_update_entity(entry.entity_id, **updates)
