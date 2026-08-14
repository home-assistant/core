"""The TrueNAS integration."""

from __future__ import annotations

import functools
from logging import getLogger
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_NAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .const import (
    BEHAVIOR_REMOVE_INACTIVE_NIC,
    CONF_BEHAVIORS,
    CONF_DATA_UNIT,
    CONF_DATASET_PASSPHRASES,
    CONF_MONITORED_GROUPS,
    DEFAULT_ALERT_PROPERTIES,
    DEFAULT_BEHAVIORS,
    DEFAULT_DATA_UNIT,
    DEFAULT_MONITORED_GROUPS,
    DOMAIN,
    GROUP_DATA_PATHS,
    PLATFORMS,
    SCHEMA_SERVICE_ALERT_DISMISS,
    SCHEMA_SERVICE_ALERT_LIST,
    SCHEMA_SERVICE_ALERT_RESTORE,
    SCHEMA_SERVICE_PASSPHRASE_LIST,
    SCHEMA_SERVICE_PASSPHRASE_REMOVE,
    SERVICE_ALERT_CONFIG_ENTRY,
    SERVICE_ALERT_DISMISS,
    SERVICE_ALERT_LIST,
    SERVICE_ALERT_PROPERTIES,
    SERVICE_ALERT_RESTORE,
    SERVICE_ALERT_UUID,
    SERVICE_CONFIG_ENTRY,
    SERVICE_PASSPHRASE_DATASET_PATH,
    SERVICE_PASSPHRASE_LIST,
    SERVICE_PASSPHRASE_REMOVE,
    SIGNAL_UPDATE_SENSORS,
)
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import (
    TrueNASEntityDescription,
    _composite_references,
    _is_uid_excluded,
    format_unique_id,
    register_system_device,
)
from .helper import alert_action, scaled_data_unit
from .migration import (
    async_adopt_legacy_entities,
    async_notify_migration_result,
    finalize_legacy_adoption,
    pending_legacy_records,
)
from .sensor_types import SENSOR_TYPES, TrueNASSensorEntityDescription

_LOGGER = getLogger(__name__)

# This integration is config-entry only; it has no configuration.yaml schema.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# All entity descriptions across platforms, used to compute the set of unique_ids
# that legitimately exist for the current TrueNAS objects (orphan cleanup).
_ALL_DESCRIPTIONS = SENSOR_TYPES


# ---------------------------
#   _migrate_data_size_units
# ---------------------------
def _migrate_data_size_units(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    coordinator: TrueNASCoordinator,
) -> None:
    """Force each DATA_SIZE sensor's display unit from the base and magnitude.

    The unit is derived from the configured base (GB/GiB) and the entity's
    current value, then written directly to the entity registry on every startup
    so the GB/GiB preference takes effect and the unit tracks the value (e.g. a
    pool is shown in TiB once it exceeds 1 TiB).
    """
    data_unit = config_entry.options.get(
        CONF_DATA_UNIT, config_entry.data.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT)
    )
    binary = data_unit == "GiB"
    inst = config_entry.data[CONF_NAME]
    ent_reg = er.async_get(hass)

    for description in SENSOR_TYPES:
        if getattr(description, "device_class", None) == SensorDeviceClass.DATA_SIZE:
            _migrate_description(ent_reg, coordinator, inst, description, binary)


def _migrate_description(
    ent_reg: er.EntityRegistry,
    coordinator: TrueNASCoordinator,
    inst: str,
    description: TrueNASSensorEntityDescription,
    binary: bool,
) -> None:
    """Force units for all entities produced by a single DATA_SIZE description."""
    data = coordinator.ds.get(description.data_path or "")
    if not isinstance(data, dict):
        return

    if not description.data_reference:
        value = data.get(description.data_attribute or "")
        _force_entity_unit(ent_reg, inst, description, None, value, binary)
        return

    for uid, vals in data.items():
        if not isinstance(vals, dict):
            continue
        ref = vals.get(description.data_reference)
        _force_entity_unit(
            ent_reg,
            inst,
            description,
            ref if ref is not None else uid,
            vals.get(description.data_attribute),
            binary,
        )


def _force_entity_unit(
    ent_reg: er.EntityRegistry,
    inst: str,
    description: TrueNASSensorEntityDescription,
    reference: Any,
    value: Any,
    binary: bool,
) -> None:
    """Write the magnitude-appropriate display unit of one entity to the registry."""
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, format_unique_id(inst, description.key, reference)
    )
    if entity_id is None:
        return

    unit, _ = scaled_data_unit(value, binary)
    entry = ent_reg.async_get(entity_id)
    options = dict(entry.options.get("sensor", {})) if entry else {}
    if options.get("unit_of_measurement") != unit:
        options["unit_of_measurement"] = unit
        ent_reg.async_update_entity_options(entity_id, "sensor", options)


# ---------------------------
#   _collect_active_unique_ids / _cleanup_orphaned_entities
# ---------------------------
def _handle_keyless(
    base: str, is_disabled: bool, active: set[str], live_bases: set[str]
) -> None:
    """Route a keyless entity base to the correct set for the cleanup decision."""
    if is_disabled:
        live_bases.add(base)
    else:
        active.add(base)


def _referenced_unique_ids(
    inst: str,
    description: TrueNASEntityDescription,
    data: dict[str, Any],
    honor_exclude: bool = True,
) -> set[str]:
    """Unique_ids the integration would create for one referenced description.

    Mirrors entity creation; the ``data_exclude`` filter (e.g. traffic sensors
    of a down interface) is only applied when ``honor_exclude`` is True.
    """
    ids: set[str] = set()
    for uid, vals in data.items():
        if honor_exclude and _is_uid_excluded(description, vals):
            continue
        ref = vals.get(description.data_reference)
        reference = ref if ref is not None else uid
        ids.add(format_unique_id(inst, description.key, reference))

    return ids


def _collect_active_unique_ids(
    inst: str, coordinator: TrueNASCoordinator
) -> tuple[set[str], set[str]]:
    """Return (active unique_ids, live bases) for the current TrueNAS objects.

    ``active`` is every unique_id the integration would create right now (see
    ``_referenced_unique_ids``). The ``data_exclude`` filter (e.g. traffic
    sensors of down interfaces) is only honoured when the
    BEHAVIOR_REMOVE_INACTIVE_NIC option is active; otherwise excluded entities
    are kept. ``live bases`` are the per-description id prefixes whose data
    domain currently holds data, so cleanup never wipes a whole group on a
    transient empty fetch.
    """
    behaviors = coordinator.config_entry.options.get(CONF_BEHAVIORS, DEFAULT_BEHAVIORS)
    honor_exclude = BEHAVIOR_REMOVE_INACTIVE_NIC in behaviors

    monitored = coordinator.config_entry.options.get(
        CONF_MONITORED_GROUPS, DEFAULT_MONITORED_GROUPS
    )
    disabled_data_paths = _build_disabled_data_paths(monitored)

    active: set[str] = set()
    live_bases: set[str] = set()

    for description in _ALL_DESCRIPTIONS:
        _process_static_description(
            inst,
            description,
            disabled_data_paths,
            honor_exclude,
            active,
            live_bases,
            coordinator.data,
        )

    for description in _ALL_DESCRIPTIONS:
        new_active, new_live_bases = _process_dynamic_description(
            inst,
            description,
            coordinator.data,
            honor_exclude,
            disabled_data_paths,
        )
        active |= new_active
        live_bases |= new_live_bases

    return active, live_bases


def _build_disabled_data_paths(monitored: list[str]) -> set[str]:
    """Return the set of data paths for groups that are not monitored.

    GROUP_DATA_PATHS maps each monitor group to its top-level coordinator data
    key(s). Any group absent from ``monitored`` contributes its paths here so
    downstream entity creation can skip disabled domains.
    """
    disabled: set[str] = set()
    for group, paths in GROUP_DATA_PATHS.items():
        if group not in monitored:
            disabled.update(paths)
    return disabled


def _process_static_description(
    inst: str,
    description: TrueNASEntityDescription,
    disabled_data_paths: set[str],
    honor_exclude: bool,
    active: set[str],
    live_bases: set[str],
    data: dict[str, Any],
) -> None:
    """Process one static (data_dynamic_keys=False) description.

    Populates ``active`` with unique_ids for referenced objects that currently
    exist, and ``live_bases`` with the base unique_id when the data path is
    present. Keyless descriptions are handled by ``_handle_keyless``; referenced
    descriptions are expanded via ``_referenced_unique_ids``.
    """
    base = format_unique_id(inst, description.key)
    is_disabled_group = description.data_path in disabled_data_paths

    if not getattr(description, "data_reference", None):
        _handle_keyless(base, is_disabled_group, active, live_bases)
        return

    sub_data = data.get(description.data_path or "")
    if not sub_data and not is_disabled_group:
        return

    live_bases.add(base)
    if sub_data and not is_disabled_group:
        active |= _referenced_unique_ids(inst, description, sub_data, honor_exclude)


def _process_dynamic_description(
    inst: str,
    description: TrueNASEntityDescription,
    data: dict[str, Any],
    honor_exclude: bool,
    disabled_data_paths: set[str],
) -> tuple[set[str], set[str]]:
    """Return (new active ids, live bases) for one dynamic-key description.

    For ``data_dynamic_keys=True`` descriptions the top-level data mapping key
    becomes the entity uid. If ``data_composite_references`` is set, the leaf
    key from each nested object is appended (``uid::ref``); otherwise the
    referenced unique_ids are computed directly.
    """
    if not getattr(description, "data_dynamic_keys", False):
        return set(), set()

    base = format_unique_id(inst, description.key)
    live_bases: set[str] = {base}

    is_disabled_group = description.data_path in disabled_data_paths
    if is_disabled_group:
        return set(), live_bases

    ref = getattr(description, "data_reference", None)
    if not ref:
        return set(), live_bases

    sub_data = data.get(description.data_path or "")
    if not sub_data:
        # Transient empty fetch of the whole domain: report no live base, so
        # cleanup leaves the existing entities alone (same rule as
        # ``_process_static_description``). Reporting the base as live here
        # wiped every registry entry of the domain on each restart, because
        # "live but nothing active" means "all of them are orphans".
        return set(), set()

    active: set[str] = set()
    if getattr(description, "data_composite_references", ()):
        active |= _composite_references(inst, description, sub_data, honor_exclude)
    else:
        active |= _referenced_unique_ids(inst, description, sub_data, honor_exclude)

    return active, live_bases


# ---------------------------
#   Alert Service Handlers
# ---------------------------
def _resolve_config_entry(
    hass: HomeAssistant, entry_id: str | None
) -> tuple[TrueNASConfigEntry | None, dict[str, Any]]:
    """Resolve the target config entry; return (entry, {}) or (None, error_dict).

    Services are registered in ``async_setup`` (before any entry exists), so the
    target entry is validated here at call time: it must exist and be loaded.
    """
    entries: list[TrueNASConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    loaded = [entry for entry in entries if entry.state is ConfigEntryState.LOADED]

    if entry_id:
        for entry in entries:
            if entry.entry_id != entry_id:
                continue
            if entry.state is not ConfigEntryState.LOADED:
                return None, {
                    "error": (
                        f"TrueNAS instance {entry_id} is not loaded "
                        f"(state: {entry.state.value})"
                    ),
                    "translation_key": "config_entry_not_loaded",
                    "translation_placeholders": {
                        "entry_id": entry_id,
                        "state": entry.state.value,
                    },
                }
            return entry, {}
        return None, {
            "error": f"TrueNAS instance {entry_id} not found",
            "translation_key": "config_entry_not_found",
            "translation_placeholders": {"entry_id": entry_id},
        }

    if not loaded:
        return None, {
            "error": "No TrueNAS instances configured",
            "translation_key": "no_config_entries",
            "translation_placeholders": {},
        }
    if len(loaded) != 1:
        return (
            None,
            {
                "error": (
                    f"Multiple TrueNAS instances ({len(loaded)}); "
                    "please specify config_entry"
                ),
                "translation_key": "multiple_config_entries",
                "translation_placeholders": {"count": str(len(loaded))},
            },
        )
    return loaded[0], {}


def _require_config_entry(
    hass: HomeAssistant, entry_id: str | None
) -> TrueNASConfigEntry:
    """Resolve the target config entry for a void service, raising on failure.

    Centralizes the error-dict-to-exception translation that every void
    service handler previously repeated after calling ``_resolve_config_entry``.
    """
    entry, error = _resolve_config_entry(hass, entry_id)
    if error or entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=error["translation_key"],
            translation_placeholders=error["translation_placeholders"],
        )
    return entry


async def _handle_alert_list(hass: HomeAssistant, call: ServiceCall) -> dict[str, Any]:
    """List all TrueNAS alerts with selectable properties."""
    entry, error = _resolve_config_entry(
        hass, call.data.get(SERVICE_ALERT_CONFIG_ENTRY)
    )
    if error or entry is None:
        return {"alerts": [], "error": error["error"]}

    alerts = await entry.runtime_data.api.query("alert.list")
    if not isinstance(alerts, list):
        return {"alerts": [], "error": "Unexpected alert.list response"}

    # Filter properties if specified
    props = call.data.get(SERVICE_ALERT_PROPERTIES, DEFAULT_ALERT_PROPERTIES)
    if props == "*":
        return {"alerts": alerts}

    prop_list = [p.strip() for p in props.split(",")]
    filtered = [{k: a[k] for k in prop_list if k in a} for a in alerts]
    return {"alerts": filtered}


async def _handle_alert_dismiss(hass: HomeAssistant, call: ServiceCall) -> None:
    """Dismiss a TrueNAS alert by UUID."""
    entry = _require_config_entry(hass, call.data.get(SERVICE_ALERT_CONFIG_ENTRY))

    if uuid := call.data.get(SERVICE_ALERT_UUID):
        await alert_action(entry.runtime_data, uuid, "dismiss")
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_alert_uuid",
            translation_placeholders={"action": "dismiss"},
        )


async def _handle_alert_restore(hass: HomeAssistant, call: ServiceCall) -> None:
    """Restore a TrueNAS alert by UUID."""
    entry = _require_config_entry(hass, call.data.get(SERVICE_ALERT_CONFIG_ENTRY))

    if uuid := call.data.get(SERVICE_ALERT_UUID):
        await alert_action(entry.runtime_data, uuid, "restore")
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="missing_alert_uuid",
            translation_placeholders={"action": "restore"},
        )


async def _handle_passphrase_remove(hass: HomeAssistant, call: ServiceCall) -> None:
    """Remove a stored dataset passphrase by dataset path."""
    entry = _require_config_entry(hass, call.data.get(SERVICE_CONFIG_ENTRY))

    dataset_path = call.data.get(SERVICE_PASSPHRASE_DATASET_PATH, "").strip()
    if not dataset_path:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="missing_dataset_path"
        )

    existing = entry.data.get(CONF_DATASET_PASSPHRASES, {})
    if not isinstance(existing, dict) or dataset_path not in existing:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="passphrase_not_found",
            translation_placeholders={"dataset": dataset_path},
        )
    updated = {k: v for k, v in existing.items() if k != dataset_path}
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_DATASET_PASSPHRASES: updated},
    )


async def _handle_passphrase_list(
    hass: HomeAssistant, call: ServiceCall
) -> dict[str, Any]:
    """Return the dataset names that have a stored passphrase (no values)."""
    entry, error = _resolve_config_entry(hass, call.data.get(SERVICE_CONFIG_ENTRY))
    if error or entry is None:
        return {"datasets": [], "error": error["error"]}

    stored = entry.data.get(CONF_DATASET_PASSPHRASES, {})
    datasets = sorted(stored.keys()) if isinstance(stored, dict) else []
    return {"datasets": datasets}


# ---------------------------
#   async_setup
# ---------------------------
async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the domain-level services.

    Registration happens at integration setup (not per config entry) so the
    services exist independently of any entry; the handlers resolve and
    validate the target entry at call time (see ``_resolve_config_entry``).

    Each ``_handle_*`` function takes ``hass`` as its first argument only to
    receive it as a bound ``functools.partial`` here; the domain-level
    handlers below are thin wrappers with no logic of their own beyond that.
    """
    hass.services.async_register(
        DOMAIN,
        SERVICE_ALERT_DISMISS,
        functools.partial(_handle_alert_dismiss, hass),
        schema=SCHEMA_SERVICE_ALERT_DISMISS,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ALERT_RESTORE,
        functools.partial(_handle_alert_restore, hass),
        schema=SCHEMA_SERVICE_ALERT_RESTORE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ALERT_LIST,
        functools.partial(_handle_alert_list, hass),
        schema=SCHEMA_SERVICE_ALERT_LIST,
        supports_response=SupportsResponse.OPTIONAL,
    )
    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_PASSPHRASE_REMOVE,
        functools.partial(_handle_passphrase_remove, hass),
        schema=SCHEMA_SERVICE_PASSPHRASE_REMOVE,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_PASSPHRASE_LIST,
        functools.partial(_handle_passphrase_list, hass),
        schema=SCHEMA_SERVICE_PASSPHRASE_LIST,
        supports_response=SupportsResponse.OPTIONAL,
    )

    return True


# ---------------------------
#   async_setup_entry
# ---------------------------
async def async_setup_entry(
    hass: HomeAssistant, config_entry: TrueNASConfigEntry
) -> bool:
    """Set up TrueNAS config entry."""
    coordinator = TrueNASCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
    coordinator.system_device_id = register_system_device(
        hass, config_entry, coordinator
    )

    # Community-Edition rename: free the legacy "truenas" entity_ids before the
    # platforms create the new entities (no-op until the domain is renamed).
    adopted = await async_adopt_legacy_entities(hass, config_entry)

    _migrate_data_size_units(hass, config_entry, coordinator)

    # Orphaned-entity/empty-device cleanup runs from entity.async_add_entities
    # instead, *after* each platform's own entities are (re)added -- doing it
    # here first would see the System device just created above with zero
    # entities yet and delete it before the platforms below ever attach one.
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Re-attach the freed legacy entity_ids now that the new entities exist.
    # pending_legacy_records() re-derives this from *all* persisted records on
    # every setup (not just this run's freshly adopted ones), so a record left
    # pending on an earlier setup -- its entity was disabled or its monitored
    # group off, so it did not exist yet -- still reclaims its id once that
    # entity is finally created, without ever re-touching an already-resolved
    # (or since manually renamed) one.
    finalize_legacy_adoption(
        hass, config_entry, pending_legacy_records(hass, config_entry)
    )
    async_notify_migration_result(hass, config_entry, adopted)

    # Re-run entity discovery on every coordinator refresh so entities for newly
    # appearing objects (e.g. a network interface coming up, a new pool/dataset)
    # are created without requiring an integration reload. The discovery handler
    # (entity.async_add_entities) expects the coordinator as its argument and does
    # not request another refresh, so this does not create a refresh loop.
    @callback
    def _handle_coordinator_refresh() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE_SENSORS, coordinator)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_handle_coordinator_refresh)
    )

    return True


# ---------------------------
#   async_unload_entry
# ---------------------------
async def async_unload_entry(
    hass: HomeAssistant, config_entry: TrueNASConfigEntry
) -> bool:
    """Unload TrueNAS config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    ):
        coordinator = get_truenas_coordinator(config_entry)
        if coordinator is not None:
            await coordinator.stop_app_stats()
            await coordinator.api.close()
        if hasattr(config_entry, "runtime_data"):
            del config_entry.runtime_data

    return unload_ok
