"""TrueNAS HA shared entity model."""

from asyncio import Lock
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
import inspect
from logging import getLogger
from typing import Any, cast, override

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION, CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_platform as ep
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription
from homeassistant.helpers.service import async_register_platform_entity_service
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import _summarize_payload
from .const import (
    ATTRIBUTION,
    BEHAVIOR_REMOVE_INACTIVE_NIC,
    CONF_BEHAVIORS,
    CONF_SYSTEM_ID,
    DEFAULT_BEHAVIORS,
    DOMAIN,
    SIGNAL_UPDATE_SENSORS,
)
from .coordinator import TrueNASCoordinator, get_truenas_coordinator
from .helper import format_attribute

_LOGGER = getLogger(__name__)

_UNKNOWN_KEY = "<unknown>"


def resolve_entry_identity(config_entry: ConfigEntry) -> str:
    """Return a stable per-entry identity string for unique_ids/device identifiers.

    Prefers CONF_SYSTEM_ID (the TrueNAS system.global.id UUID, only populated
    when that lookup succeeded during setup); falls back to the config
    entry's own entry_id, which HA guarantees unique and stable for the
    entry's lifetime. Never use CONF_NAME (the user-editable display name)
    for this purpose -- two entries can share a display name, which would
    otherwise collide entities/devices across different TrueNAS servers.
    """
    system_id = config_entry.data.get(CONF_SYSTEM_ID)
    if isinstance(system_id, str) and system_id:
        return system_id
    return config_entry.entry_id


def format_unique_id(identity: str, key: str, reference: object = None) -> str:
    """Build an entity unique_id from the entry identity, key and reference.

    ``identity`` must be a stable per-entry identity (see
    ``resolve_entry_identity``), not the user-editable display name.

    ``reference`` keeps its original case and is not slugified: unique_id has
    no character restrictions in HA, and both slugify() and lower() are lossy
    -- slugify's '/'/'-'/'_' collapsing and lower()'s case-folding would each
    let distinct references (e.g. ZFS datasets "tank/a-b" vs "tank/a_b", or
    "tank/Data" vs "tank/data") collide and silently drop one entity as a
    duplicate.
    """
    base = f"{identity.lower()}-{key}"
    if reference is None:
        return base
    return f"{base}-{reference!s}"


def format_device_identifier(identity: str) -> str:
    """Build the main TrueNAS ("System") device identifier value.

    ``identity`` must be a stable per-entry identity (see
    ``resolve_entry_identity``), not the user-editable display name. Uses
    ``identity`` alone -- an earlier format also appended the TrueNAS
    hostname, but hostname is user-editable (System Settings > General)
    while identity is already stable, so renaming the TrueNAS host would
    have silently orphaned this device and created a duplicate. Shared so
    other platforms (e.g. the statistics-cleanup button) reuse it.
    """
    return identity


@lru_cache(maxsize=1)
def _supports_via_device_id() -> bool:
    """Whether the running HA Core's device registry accepts via_device_id.

    Added in HA Core 2026.8; older cores raise TypeError on the kwarg.
    """
    return (
        "via_device_id"
        in inspect.signature(dr.DeviceRegistry.async_get_or_create).parameters
    )


def register_system_device(
    hass: HomeAssistant, config_entry: ConfigEntry, coordinator: TrueNASCoordinator
) -> str:
    """Register (or fetch) the "System" device and return its registry id.

    Other devices link via coordinator.system_device_id, not via_device
    (deprecated in HA Core 2027.8.0 since identifiers are no longer unique
    across config entries).
    """
    inst = coordinator.config_entry.data[CONF_NAME]
    identity = resolve_entry_identity(coordinator.config_entry)
    identifier = format_device_identifier(identity)
    system_info = coordinator.data["system_info"]
    http_scheme = "https" if coordinator.api.scheme == "wss" else "http"
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, identifier)},
        name=inst,
        model=f"{system_info['system_product']}",
        manufacturer=f"{system_info['system_manufacturer']}",
        sw_version=f"{system_info['version']}",
        configuration_url=f"{http_scheme}://{config_entry.data[CONF_HOST]}",
    )
    return device.id


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
        """Validate flag/reference combos; warns instead of raising so bad configs fail fast without crashing at import time."""
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
    identity: str,
    description: TrueNASEntityDescription,
    data: dict[str, Any],
    honor_exclude: bool = True,
) -> set[str]:
    """Compute unique_ids for descriptions whose reference is nested in a list.

    Builds ``identity-key-uid::leaf`` ids from ``data[uid][container_key][*][leaf_key]``,
    e.g. per-NIC sensors. ``identity`` must be a stable per-entry identity
    (see ``resolve_entry_identity``), not the user-editable display name.
    """
    ids: set[str] = set()
    if len(description.data_composite_references) != 2:
        return ids
    container_key, leaf_key = description.data_composite_references
    for uid, vals in data.items():
        container = _get_composite_container(vals, container_key)
        if container is None:
            continue
        for item in container:
            ref = _extract_composite_ref(item, description, honor_exclude, leaf_key)
            if ref is not None:
                ids.add(format_unique_id(identity, description.key, f"{uid}::{ref}"))
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


def _skip_keyless_description(
    entity_description: TrueNASEntityDescription, data: dict[str, Any]
) -> bool:
    """Return True if a keyless description has no value to expose."""
    attr_name = getattr(entity_description, "data_attribute", None) or getattr(
        entity_description, "data_is_on", None
    )
    return data.get(attr_name) is None if attr_name else False


def _is_uid_excluded(entity_description: TrueNASEntityDescription, vals: Any) -> bool:
    """Return True if description.data_exclude (key, value) matches, e.g. to skip sensors for a down NIC."""
    data_exclude = getattr(entity_description, "data_exclude", None)
    if not data_exclude:
        return False

    key, value = data_exclude
    return isinstance(vals, dict) and vals.get(key) == value


def _new_referenced_entities(
    coordinator: TrueNASCoordinator,
    entity_description: TrueNASEntityDescription,
    data: Mapping[str, Any],
    dispatcher: Mapping[str, Callable[..., Any]],
    seen: set[str],
) -> list[TrueNASEntity]:
    """Collect new per-uid entities for one referenced (multi-object) description."""
    behaviors = coordinator.config_entry.options.get(CONF_BEHAVIORS, DEFAULT_BEHAVIORS)
    apply_exclude = BEHAVIOR_REMOVE_INACTIVE_NIC in behaviors
    new_entities: list[TrueNASEntity] = []
    for uid, vals in data.items():
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

    ``seen`` holds ids already registered so existing entities are never re-added.
    """
    new_entities: list[TrueNASEntity] = []
    for entity_description in descriptions:
        if entity_description.func == "TrueNASAppStatsSensor":
            continue
        data = coordinator.data.get(entity_description.data_path or "")
        if data is None:
            continue
        if not isinstance(data, dict):
            # Otherwise AttributeError in the .get() calls below.
            _LOGGER.debug(
                "Skipping non-dict coordinator payload for data_path %s"
                " (entity description key %s): %s",
                entity_description.data_path or "",
                entity_description.key,
                _summarize_payload(data),
            )
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


async def async_add_entities(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    dispatcher: Mapping[str, Callable[..., Any]],
) -> None:
    """Set up the platform and register dynamic entity discovery.

    Diffs against the live ``platform.entities`` (not the persistent entity
    registry, and not a platform-lifetime set) so new/removed objects are
    (re)added correctly across startup, steady state, and runtime removal.
    """
    platform = ep.async_get_current_platform()
    services = getattr(platform.platform, "SENSOR_SERVICES", [])
    descriptions = getattr(platform.platform, "SENSOR_TYPES", [])

    for service in services:
        if hass.services.has_service(platform.platform_name, service.name):
            continue
        async_register_platform_entity_service(
            hass,
            platform.platform_name,
            service.name,
            admin_only=service.admin_only,
            entity_domain=platform.domain,
            func=service.action,
            schema=service.schema,
        )

    add_lock = Lock()

    # Always set as runtime_data before platforms load; guard so a future
    # contract change fails loudly instead of via AttributeError deep in setup.
    this_coordinator = get_truenas_coordinator(config_entry)
    if this_coordinator is None:
        _LOGGER.error(
            "No TrueNAS coordinator found for entry %s; skipping entity setup",
            config_entry.entry_id,
        )
        return

    async def async_update_controller(coordinator: TrueNASCoordinator) -> None:
        """Add entities for newly-appeared objects on each coordinator refresh."""

        # Ignore refreshes from other config entries (SIGNAL_UPDATE_SENSORS fans
        # out to every platform) to avoid duplicate-entity errors (#33).
        if coordinator is not this_coordinator:
            return

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
        self._identity = resolve_entry_identity(coordinator.config_entry)
        self._config_entry = self.coordinator.config_entry
        self._attr_extra_state_attributes = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._uid = uid
        self._refresh_data()

    def _refresh_data(self) -> None:
        """Refresh cached data from the coordinator for this entity."""
        data = self.coordinator.data.get(self.entity_description.data_path or "", {})
        if not isinstance(data, dict):
            # parse_api() always returns a dict; guard anyway so malformed
            # data can't crash the entity instead of just rendering unavailable.
            data = {}
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

        Isolates this entity's one touch of the private attribute so a
        future HA core rename only needs a fix here.
        """
        return getattr(self, "_name_translation_key", None)

    def _translated_description_name(self) -> str | None:
        """Resolve the description's name, preferring loaded translations.

        This entity builds its own name instead of using HA's has_entity_name
        machinery, so the translation lookup is triggered manually; desc_name
        is only a fallback for descriptions that set `name` explicitly.
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
            return format_unique_id(
                self._identity, self.entity_description.key, reference
            )

        return format_unique_id(self._identity, self.entity_description.key)

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return a description for device registry."""
        ha_group = self.entity_description.ha_group or ""
        dev_connection = DOMAIN
        dev_connection_value = f"{self._identity}_{ha_group}"
        dev_group = ha_group
        if ha_group == "System":
            dev_connection_value = format_device_identifier(self._identity)

        if ha_group.startswith("data__"):
            dev_group = ha_group[6:]
            if dev_group in self._data:
                dev_group = self._data[dev_group]
                dev_connection_value = f"{self._identity}_{dev_group}"

        if self.entity_description.ha_connection:
            dev_connection = self.entity_description.ha_connection

        if self.entity_description.ha_connection_value:
            dev_connection_value = self.entity_description.ha_connection_value
            if dev_connection_value.startswith("data__"):
                data_key = dev_connection_value[6:]
                connection_val = self._data.get(data_key, "unknown")
                dev_connection_value = f"{self._identity}_{connection_val}"

        if ha_group == "System":
            http_scheme = "https" if self.coordinator.api.scheme == "wss" else "http"
            return DeviceInfo(
                identifiers={(dev_connection, f"{dev_connection_value}")},
                name=self._inst,
                model=f"{self.coordinator.data['system_info']['system_product']}",
                manufacturer=f"{self.coordinator.data['system_info']['system_manufacturer']}",
                sw_version=f"{self.coordinator.data['system_info']['version']}",
                configuration_url=f"{http_scheme}://{self.coordinator.config_entry.data[CONF_HOST]}",
            )

        # Plain dict, not DeviceInfo: via_device_id was only added to that
        # TypedDict in HA Core 2026.8 (see _supports_via_device_id()), and
        # DEVICE_INFO_TYPES only allows default_name/model/manufacturer with
        # "connections", not "identifiers" -- so plain name/model/manufacturer
        # keys are required here instead.
        system_info = self.coordinator.data["system_info"]
        device_info: dict[str, Any] = {
            "identifiers": {(dev_connection, f"{dev_connection_value}")},
            "name": f"{self._inst} {dev_group}",
            "model": f"{system_info['system_product']}",
            "manufacturer": f"{system_info['system_manufacturer']}",
        }
        system_device_id = self.coordinator.system_device_id
        if _supports_via_device_id() and system_device_id is not None:
            device_info["via_device_id"] = system_device_id
        else:
            device_info["via_device"] = (
                DOMAIN,
                format_device_identifier(self._identity),
            )
        return cast(DeviceInfo, device_info)

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

        Entity services are platform-wide, so an unimplemented action (e.g.
        restart on an app) needs a clear error instead of NotImplementedError.
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

        query() swallows errors and returns None (also a valid success value
        for some endpoints), so only a non-empty api.error (reset each call)
        signals an actual failure.
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
