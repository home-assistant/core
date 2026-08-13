"""TrueNAS HA shared entity model."""

from __future__ import annotations

import inspect
from asyncio import Lock
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from logging import getLogger
from typing import Any, cast, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_platform as ep
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    ATTRIBUTION,
    BEHAVIOR_REMOVE_INACTIVE_NIC,
    CONF_BEHAVIORS,
    DEFAULT_BEHAVIORS,
    DOMAIN,
    SIGNAL_UPDATE_SENSORS,
)
from .coordinator import TrueNASCoordinator, get_truenas_coordinator
from .helper import format_attribute

_LOGGER = getLogger(__name__)

_UNKNOWN_KEY = "<unknown>"


# ---------------------------
#   format_unique_id
# ---------------------------
def format_unique_id(inst: str, key: str, reference: object = None) -> str:
    """Build an entity unique_id from instance name, description key and reference.

    Shared so the migration in __init__.py can resolve the same unique_id an
    entity produces.
    """
    base = f"{inst.lower()}-{key}"
    if reference is None:
        return base
    return f"{base}-{slugify(str(reference).lower())}"


def format_device_identifier(inst: str, hostname: str) -> str:
    """Build the main TrueNAS ("System") device identifier value.

    Shared so other platforms (e.g. the diagnostic statistics-cleanup button)
    associate with the existing device instead of duplicating the format.
    """
    return f"{inst}_{hostname}"


@lru_cache(maxsize=1)
def _supports_via_device_id() -> bool:
    """Whether the running HA Core's device registry accepts via_device_id.

    ``via_device_id`` was only added to ``DeviceRegistry.async_get_or_create``
    in HA Core 2026.8 -- passing it as a kwarg on an older Core raises
    TypeError there, so it can only be used once detected as supported.
    ``via_device`` (the older identifiers-tuple form) keeps working
    everywhere until it is removed in 2027.8.0, so older installs fall back
    to it. Cached: this cannot change while the process is running.
    """
    return (
        "via_device_id"
        in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
    )


def register_system_device(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: TrueNASCoordinator
) -> str:
    """Register (or fetch) the "System" device and return its registry id.

    Called once from ``async_setup_entry`` after the coordinator's first
    refresh, before platforms create entities. Every other device links to
    it via ``coordinator.system_device_id`` (``via_device_id``) instead of
    resolving it itself -- ``via_device`` (an identifiers tuple) is
    deprecated as of HA Core 2027.8.0 because identifiers are no longer
    unique across config entries.
    """
    inst = coordinator.config_entry.data[CONF_NAME]
    system_info = coordinator.data["system_info"]
    identifier = format_device_identifier(inst, system_info["hostname"])
    http_scheme = "https" if coordinator.api.scheme == "wss" else "http"
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(DOMAIN, identifier)},
        identifiers={(DOMAIN, identifier)},
        name=inst,
        model=f"{system_info['system_product']}",
        manufacturer=f"{system_info['system_manufacturer']}",
        sw_version=f"{system_info['version']}",
        configuration_url=f"{http_scheme}://{config_entry.data[CONF_HOST]}",
    )
    return device.id


# ---------------------------
#   TrueNASEntityDescription
# ---------------------------
# Dynamic vs static entity contract:
#   - Static descriptions (data_dynamic_keys=False) have a fixed data_path and
#     produce either one keyless entity or one entity per referenced object.
#   - Dynamic descriptions (data_dynamic_keys=True) use top-level data keys as
#     entity UIDs, allowing arbitrary objects to become entities.
#   - Composite references (data_composite_references=(container, leaf)) add a
#     second level of dynamism: the leaf value from each nested object becomes
#     part of the composite UID (``uid::leaf``), used for per-subobject entities
#     like per-NIC network sensors.
@dataclass(frozen=True, kw_only=True)
class TrueNASEntityDescription(EntityDescription):
    """Fields shared by the entity descriptions of every TrueNAS platform."""

    ha_group: str | None = None
    ha_connection: str | None = None
    ha_connection_value: str | None = None
    data_path: str | None = None
    data_name: str | None = None
    data_uid: str | None = None
    data_reference: str | None = None
    data_attributes_list: tuple[str, ...] = ()
    data_dynamic_keys: bool = False
    data_composite_references: tuple[str, ...] = ()
    func: str = ""

    def __post_init__(self) -> None:
        """Validate combinations of dynamic flags and references.

        Invalid configurations emit warnings so they fail fast in tests/CI
        without crashing the integration at import time.
        """
        composite = self.data_composite_references or ()
        has_composite = bool(composite)
        dynamic = self.data_dynamic_keys

        if has_composite and not dynamic:
            _LOGGER.warning(
                "Invalid TrueNASEntityDescription %r: "
                "data_composite_references requires data_dynamic_keys=True",
                getattr(self, "key", _UNKNOWN_KEY),
            )
            return

        if has_composite and len(composite) != 2:
            _LOGGER.warning(
                "Invalid TrueNASEntityDescription %r: "
                "data_composite_references must contain exactly two segments "
                "(container_key, leaf_key)",
                getattr(self, "key", _UNKNOWN_KEY),
            )
            return

        if dynamic and not self.data_reference and not has_composite:
            _LOGGER.warning(
                "Invalid TrueNASEntityDescription %r: "
                "data_dynamic_keys=True requires either data_reference or "
                "data_composite_references",
                getattr(self, "key", _UNKNOWN_KEY),
            )


def _composite_references(
    inst: str,
    description: TrueNASEntityDescription,
    data: dict[str, Any],
    honor_exclude: bool = True,
) -> set[str]:
    """Compute unique_ids for descriptions whose reference is nested inside a list.

    For each top-level uid in ``data``, the leaf value at
    ``data[uid][container_key][item][leaf_key]`` becomes a composite unique_id
    of the form ``inst-key-uid::ref``. This supports entities like per-NIC
    network sensors where the interface name lives inside a list of dicts.

    When ``honor_exclude`` is True, items matching ``description.data_exclude``
    are skipped, mirroring ``_referenced_unique_ids`` behavior.
    """
    ids: set[str] = set()
    container_key, leaf_key = description.data_composite_references
    for uid, vals in data.items():
        container = _get_composite_container(vals, container_key)
        if container is None:
            continue
        for item in container:
            ref = _extract_composite_ref(item, description, honor_exclude, leaf_key)
            if ref is not None:
                ids.add(format_unique_id(inst, description.key, f"{uid}::{ref}"))
    return ids


def _get_composite_container(vals: Any, container_key: str) -> list[Any] | None:
    """Return the composite container list if present and valid, else None."""
    if not isinstance(vals, dict):
        return None
    container = vals.get(container_key)
    return container if isinstance(container, list) else None


def _extract_composite_ref(
    item: Any,
    description: TrueNASEntityDescription,
    honor_exclude: bool,
    leaf_key: str,
) -> str | None:
    """Validate a composite item and return its leaf reference, or None."""
    if not isinstance(item, dict):
        return None
    if honor_exclude and _is_uid_excluded(description, item):
        return None
    ref = item.get(leaf_key)
    return ref if ref is not None else None


# ---------------------------
#   Entity discovery helpers
# ---------------------------
def _skip_keyless_description(
    entity_description: TrueNASEntityDescription, data: dict[str, Any]
) -> bool:
    """Return True if a keyless description has no value to expose."""
    attr_name: str | None = getattr(
        entity_description,
        "data_attribute",
        getattr(entity_description, "data_is_on", None),
    )
    return data.get(attr_name) is None if attr_name else False


def _is_uid_excluded(entity_description: TrueNASEntityDescription, vals: Any) -> bool:
    """Return True if a referenced object is excluded from entity creation.

    Honors an optional ``data_exclude`` (key, value) on the description, e.g. to
    skip traffic sensors for a network interface whose link is down.
    """
    data_exclude = getattr(entity_description, "data_exclude", None)
    if not data_exclude:
        return False

    key, value = data_exclude
    return isinstance(vals, dict) and vals.get(key) == value


def _new_referenced_entities(
    coordinator: TrueNASCoordinator,
    entity_description: TrueNASEntityDescription,
    data: Any,
    dispatcher: Mapping[str, Callable[..., Any]],
    seen: set[str],
) -> list[TrueNASEntity]:
    """Collect new per-uid entities for one referenced (multi-object) description."""
    behaviors = coordinator.config_entry.options.get(CONF_BEHAVIORS, DEFAULT_BEHAVIORS)
    apply_exclude = BEHAVIOR_REMOVE_INACTIVE_NIC in behaviors
    new_entities: list[TrueNASEntity] = []
    for uid in data:
        # data is a mapping of uid -> values for reference descriptions;
        # fall back to treating the iterated item itself as the values.
        vals = data[uid] if isinstance(data, dict) else uid
        if apply_exclude and _is_uid_excluded(entity_description, vals):
            continue
        obj = dispatcher[entity_description.func](coordinator, entity_description, uid)
        _append_if_new(obj, seen, new_entities)
    return new_entities


def _collect_new_entities(
    coordinator: TrueNASCoordinator,
    descriptions: Sequence[TrueNASEntityDescription],
    dispatcher: Mapping[str, Callable[..., Any]],
    seen: set[str],
) -> list[TrueNASEntity]:
    """Return entity objects whose unique_id is not in ``seen`` yet.

    ``seen`` is the set of unique_ids already registered for this config entry;
    only genuinely new objects (e.g. a freshly attached disk) are returned, so
    existing entities are never re-added.
    """
    new_entities: list[TrueNASEntity] = []
    for entity_description in descriptions:
        if entity_description.func == "TrueNASAppStatsSensor":
            continue
        data = coordinator.data.get(entity_description.data_path or "")
        if data is None:
            continue

        if entity_description.data_reference:
            new_entities += _new_referenced_entities(
                coordinator, entity_description, data, dispatcher, seen
            )
        elif not _skip_keyless_description(entity_description, data):
            obj = dispatcher[entity_description.func](coordinator, entity_description)
            _append_if_new(obj, seen, new_entities)

    return new_entities


def _append_if_new(
    obj: TrueNASEntity, seen: set[str], new_entities: list[TrueNASEntity]
) -> None:
    """Append the entity to the batch when its unique_id has not been seen yet."""
    if obj.unique_id not in seen:
        seen.add(obj.unique_id)
        new_entities.append(obj)


def _cleanup_orphaned_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    coordinator: TrueNASCoordinator,
) -> None:
    """Remove registry entities the integration would no longer create.

    An entity is deleted when it is not in the active set yet belongs to a data
    domain that currently holds data. This covers both true orphans (the object
    is gone) and entities filtered out by ``data_exclude`` (e.g. traffic sensors
    of a down interface). A transient empty fetch of a whole domain never wipes
    the corresponding group, and cleanup is skipped unless the last update
    succeeded.
    """
    from . import _collect_active_unique_ids

    if not coordinator.last_update_success:
        return

    inst = config_entry.data[CONF_NAME]
    active, live_bases = _collect_active_unique_ids(inst, coordinator)

    ent_reg = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(
        ent_reg, config_entry.entry_id
    ):
        unique_id = entity_entry.unique_id
        if unique_id in active:
            continue
        if any(
            unique_id == base or unique_id.startswith(f"{base}-") for base in live_bases
        ):
            _LOGGER.info(
                "Removing orphaned TrueNAS entity %s (unique_id=%s)",
                entity_entry.entity_id,
                unique_id,
            )
            ent_reg.async_remove(entity_entry.entity_id)

    # Remove devices that are now empty (all their entities were cleaned up above).
    dev_reg = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(
        dev_reg, config_entry.entry_id
    ):
        if not er.async_entries_for_device(
            ent_reg, device_entry.id, include_disabled_entities=True
        ):
            _LOGGER.info(
                "Removing empty TrueNAS device %s",
                device_entry.name_by_user or device_entry.name,
            )
            dev_reg.async_remove_device(device_entry.id)


async def async_add_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    dispatcher: Mapping[str, Callable[..., Any]],
) -> None:
    """Set up the platform and register dynamic entity discovery.

    On every coordinator refresh only entities that are not already loaded on the
    platform are created; existing entities refresh themselves through the
    coordinator and are never re-added (which previously caused "Platform truenas
    does not generate unique IDs" spam). The "already there" set is derived from
    the platform's currently-loaded entities (``platform.entities``) on each pass:

    * NOT from the entity registry — it persists across restarts, so on startup
      every entity would look "already there" and none would be (re)created,
      leaving them all stuck "unavailable".
    * NOT from a platform-lifetime set — an entity removed/disabled at runtime
      would then never be recreated until a reload.

    Deriving it from the live platform entities handles all three: startup
    (recreate everything), steady state (no re-add), and runtime removal (the
    object is recreated once it reappears). An asyncio lock serializes overlapping
    refreshes so an in-flight add is never duplicated.
    """
    platform = ep.async_get_current_platform()
    services = getattr(platform.platform, "SENSOR_SERVICES", [])
    descriptions = getattr(platform.platform, "SENSOR_TYPES", [])

    for service in services:
        platform.async_register_entity_service(
            service.name, service.schema, service.action
        )

    add_lock = Lock()

    # The coordinator for this config entry. __init__ stores it as runtime_data
    # before the platforms are forwarded, so it is always present; guard
    # explicitly so a future change to that contract fails loudly (logged)
    # instead of with an AttributeError deep inside platform setup.
    this_coordinator = get_truenas_coordinator(config_entry)
    if this_coordinator is None:
        _LOGGER.error(
            "No TrueNAS coordinator found for entry %s; skipping entity setup",
            config_entry.entry_id,
        )
        return

    async def async_update_controller(coordinator: TrueNASCoordinator) -> None:
        """Add entities for newly-appeared objects on each coordinator refresh."""

        # SIGNAL_UPDATE_SENSORS is a global dispatcher signal that __init__ always
        # fires with the *same* coordinator instance object (one per config entry),
        # so the identity check below is safe. With more than one TrueNAS config
        # entry every platform receives every entry's refresh, so ignore refreshes
        # from other entries — otherwise this platform would build the *other*
        # instance's entities and try to add them here, causing "Platform truenas
        # does not generate unique IDs … already exists" spam (#33).
        if coordinator is not this_coordinator:
            return

        _cleanup_orphaned_entities(hass, config_entry, coordinator)

        async with add_lock:
            loaded = {
                entity.unique_id
                for entity in platform.entities.values()
                if entity.unique_id is not None
            }
            new_entities = _collect_new_entities(
                coordinator, descriptions, dispatcher, loaded
            )
            if new_entities:
                _LOGGER.debug("Adding %d new TrueNAS entities", len(new_entities))
                await platform.async_add_entities(new_entities)

    await async_update_controller(this_coordinator)

    unsub = async_dispatcher_connect(
        hass, SIGNAL_UPDATE_SENSORS, async_update_controller
    )
    config_entry.async_on_unload(unsub)


# ---------------------------
#   TrueNASEntity
# ---------------------------
class TrueNASEntity(CoordinatorEntity[TrueNASCoordinator], Entity):
    """Define entity."""

    entity_description: TrueNASEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TrueNASCoordinator,
        entity_description: TrueNASEntityDescription,
        uid: str | None = None,
    ) -> None:
        """Initialize entity."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._inst = coordinator.config_entry.data[CONF_NAME]
        self._config_entry = self.coordinator.config_entry
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        self._refresh_data()

    def _refresh_data(self) -> None:
        """Refresh cached data from the coordinator for this entity."""
        data = self.coordinator.data.get(self.entity_description.data_path or "", {})
        self._data: dict[str, Any] = data.get(self._uid, {}) if self._uid else data
        if self._uid and not self._data:
            _LOGGER.debug(
                "Data for UID %s is missing or empty in %s",
                self._uid,
                self.entity_description.data_path,
            )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        self._refresh_data()
        super()._handle_coordinator_update()

    def _core_name_translation_key(self) -> str | None:
        """Return Entity._name_translation_key, degrading gracefully.

        Isolates the one place this entity touches a private HA-core
        implementation detail (the same cached_property HA core's own
        Entity._name_internal uses to build its lookup key), so a future
        core change that renames or removes it only needs a fix here.
        """
        return getattr(self, "_name_translation_key", None)

    def _translated_description_name(self) -> str | None:
        """Resolve the description's name, preferring loaded translations.

        This entity builds its own name (below) instead of relying on HA's
        has_entity_name machinery, so the platform-translations lookup has
        to be triggered manually. Most descriptions only set translation_key
        and leave `name` at its EntityDescription default (UNDEFINED, not a
        str), so the translation lookup must run regardless of `name` --
        `desc_name` is only a fallback for the few statically-named/unnamed
        descriptions that set `name` explicitly.
        """
        platform_translations: dict[str, str] | None = getattr(
            self.platform_data, "platform_translations", None
        )
        if platform_translations:
            name_translation_key = self._core_name_translation_key()
            translated = (
                platform_translations.get(name_translation_key)
                if name_translation_key
                else None
            )
            if translated:
                return translated

        desc_name = self.entity_description.name
        return desc_name if isinstance(desc_name, str) else None

    @property
    @override
    def name(self) -> str | None:
        """Return the name for this entity."""
        desc_name = self._translated_description_name()

        if not self._uid:
            return desc_name

        data_value = None
        if self._data is not None and self.entity_description.data_name:
            data_value = self._data.get(self.entity_description.data_name)

        if data_value is None:
            data_value = str(self._uid)

        return f"{data_value} {desc_name}" if desc_name else f"{data_value}"

    @property
    @override
    def unique_id(self) -> str:
        """Return a unique id for this entity."""
        if self._uid:
            data_ref = self.entity_description.data_reference
            value = self._data.get(data_ref) if self._data and data_ref else None
            reference = value if value is not None else self._uid
            return format_unique_id(self._inst, self.entity_description.key, reference)

        return format_unique_id(self._inst, self.entity_description.key)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        ha_group = self.entity_description.ha_group or ""
        dev_connection = DOMAIN
        dev_connection_value = f"{self._inst}_{ha_group}"
        dev_group = ha_group
        if ha_group == "System":
            dev_connection_value = format_device_identifier(
                self._inst, self.coordinator.data["system_info"]["hostname"]
            )

        if ha_group.startswith("data__"):
            dev_group = ha_group[6:]
            if dev_group in self._data:
                dev_group = self._data[dev_group]
                dev_connection_value = dev_group

        if self.entity_description.ha_connection:
            dev_connection = self.entity_description.ha_connection

        if self.entity_description.ha_connection_value:
            dev_connection_value = self.entity_description.ha_connection_value
            if dev_connection_value.startswith("data__"):
                data_key = dev_connection_value[6:]
                connection_val = self._data.get(data_key, "unknown")
                dev_connection_value = f"{self._inst}_{connection_val}"

        if ha_group == "System":
            http_scheme = "https" if self.coordinator.api.scheme == "wss" else "http"
            return DeviceInfo(
                connections={(dev_connection, f"{dev_connection_value}")},
                identifiers={(dev_connection, f"{dev_connection_value}")},
                name=self._inst,
                model=f"{self.coordinator.data['system_info']['system_product']}",
                manufacturer=f"{self.coordinator.data['system_info']['system_manufacturer']}",
                sw_version=f"{self.coordinator.data['system_info']['version']}",
                configuration_url=f"{http_scheme}://{self.coordinator.config_entry.data[CONF_HOST]}",
            )

        # A plain dict, not DeviceInfo, so the conditional via_device/via_device_id
        # key below doesn't depend on whichever DeviceInfo TypedDict shape mypy
        # happens to resolve (via_device_id was only added to it upstream in HA
        # Core 2026.8 -- see _supports_via_device_id()).
        system_info = self.coordinator.data["system_info"]
        device_info: dict[str, Any] = {
            "connections": {(dev_connection, f"{dev_connection_value}")},
            "default_name": f"{self._inst} {dev_group}",
            "default_model": f"{system_info['system_product']}",
            "default_manufacturer": f"{system_info['system_manufacturer']}",
        }
        system_device_id = self.coordinator.system_device_id
        if _supports_via_device_id() and system_device_id is not None:
            device_info["via_device_id"] = system_device_id
        else:
            device_info["via_device"] = (
                DOMAIN,
                format_device_identifier(
                    self._inst, self.coordinator.data["system_info"]["hostname"]
                ),
            )
        return cast("DeviceInfo", device_info)

    @property
    @override
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        attributes = dict(super().extra_state_attributes or {})
        for variable in self.entity_description.data_attributes_list:
            if variable in self._data:
                attributes[format_attribute(variable)] = self._data[variable]

        return attributes

    def _raise_unsupported(self, action: str) -> None:
        """Raise a clean, user-facing error for an unsupported action.

        Entity services are registered for a whole platform, so an action can be
        targeted at an entity type that does not implement it (e.g. service_restart
        on an app). Raising ServiceValidationError surfaces a clear message instead
        of an "Unknown error" from a bare NotImplementedError.
        """
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_action",
            translation_placeholders={
                "action": action,
                "entity_id": self.entity_id,
            },
        )

    def _raise_if_api_error(self, action: str) -> None:
        """Raise HomeAssistantError if the most recent api.query() call failed.

        query() swallows connection/middleware errors and returns None instead
        of raising, recording the failure in api.error; many middleware
        endpoints also legitimately return null on success, so only a
        non-empty api.error (reset at the start of every query) marks an
        actual failure.
        """
        if self.coordinator.api.error:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_failed",
                translation_placeholders={
                    "action": action,
                    "host": self.coordinator.host,
                    "error": str(self.coordinator.api.error),
                },
            )

    async def start(self) -> None:
        """Run function."""
        self._raise_unsupported("start")

    async def stop(self) -> None:
        """Stop function."""
        self._raise_unsupported("stop")

    async def restart(self) -> None:
        """Restart function."""
        self._raise_unsupported("restart")

    async def reload(self) -> None:
        """Reload function."""
        self._raise_unsupported("reload")

    async def snapshot(self) -> None:
        """Snapshot function."""
        self._raise_unsupported("snapshot")

    async def lock(self, force_umount: bool = False) -> None:
        """Lock function."""
        self._raise_unsupported("lock")

    async def unlock(
        self,
        passphrase: str | None = None,
        recursive: bool = False,
        force: bool = False,
    ) -> None:
        """Unlock function."""
        self._raise_unsupported("unlock")

    async def passphrase_set(self, passphrase: str) -> None:
        """Store passphrase function."""
        self._raise_unsupported("passphrase_set")

    async def refresh(self) -> None:
        """Refresh function."""
        self._raise_unsupported("refresh")
