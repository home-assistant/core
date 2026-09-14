"""The TrueNAS integration."""

from logging import getLogger
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_DATA_UNIT,
    DEFAULT_DATA_UNIT,
    DOMAIN,
    PLATFORMS,
    SIGNAL_UPDATE_SENSORS,
)
from .coordinator import TrueNASConfigEntry, TrueNASCoordinator, get_truenas_coordinator
from .entity import format_unique_id, register_system_device, resolve_entry_identity
from .helper import GB_SCALED_UNITS, scaled_data_unit
from .sensor_types import SENSOR_TYPES, TrueNASSensorEntityDescription

_LOGGER = getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _migrate_data_size_units(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    coordinator: TrueNASCoordinator,
) -> None:
    """Force each GB/GiB-scaled DATA_SIZE sensor's unit from the base and magnitude.

    The unit is derived from the configured base (GB/GiB) and the entity's
    current value, then written directly to the entity registry on every startup
    so the GB/GiB preference takes effect and the unit tracks the value (e.g. a
    pool is shown in TiB once it exceeds 1 TiB). Only descriptions that opt into
    this scaling (``suggested_unit_of_measurement in GB_SCALED_UNITS``) are
    touched here; DATA_SIZE sensors with a deliberately fixed suggested unit
    (e.g. app memory/block I/O in MiB) are handled by
    ``_reset_stale_forced_unit`` instead, since an older release forced them
    onto the GB/GiB scale too.
    """
    data_unit = config_entry.options.get(
        CONF_DATA_UNIT, config_entry.data.get(CONF_DATA_UNIT, DEFAULT_DATA_UNIT)
    )
    binary = data_unit == "GiB"
    identity = resolve_entry_identity(config_entry)
    ent_reg = er.async_get(hass)

    for description in SENSOR_TYPES:
        if getattr(description, "device_class", None) != SensorDeviceClass.DATA_SIZE:
            continue
        if description.suggested_unit_of_measurement in GB_SCALED_UNITS:
            _migrate_description(ent_reg, coordinator, identity, description, binary)
        else:
            _reset_stale_forced_unit(ent_reg, coordinator, identity, description)


def _description_references(
    coordinator: TrueNASCoordinator, description: TrueNASSensorEntityDescription
) -> list[tuple[Any, Any]]:
    """Return (reference, value) pairs for every entity a description produces."""
    data = coordinator.ds.get(description.data_path or "")
    if not isinstance(data, dict):
        return []

    if not description.data_reference:
        return [(None, data.get(description.data_attribute or ""))]

    pairs: list[tuple[Any, Any]] = []
    for uid, vals in data.items():
        if not isinstance(vals, dict):
            continue
        ref = vals.get(description.data_reference)
        pairs.append(
            (ref if ref is not None else uid, vals.get(description.data_attribute))
        )
    return pairs


def _migrate_description(
    ent_reg: er.EntityRegistry,
    coordinator: TrueNASCoordinator,
    identity: str,
    description: TrueNASSensorEntityDescription,
    binary: bool,
) -> None:
    """Force units for all entities produced by a single DATA_SIZE description."""
    for reference, value in _description_references(coordinator, description):
        _force_entity_unit(ent_reg, identity, description, reference, value, binary)


def _force_entity_unit(
    ent_reg: er.EntityRegistry,
    identity: str,
    description: TrueNASSensorEntityDescription,
    reference: Any,
    value: Any,
    binary: bool,
) -> None:
    """Write the magnitude-appropriate display unit of one entity to the registry."""
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, format_unique_id(identity, description.key, reference)
    )
    if entity_id is None:
        return

    unit, _ = scaled_data_unit(value, binary)
    entry = ent_reg.async_get(entity_id)
    options = dict(entry.options.get("sensor", {})) if entry else {}
    if options.get("unit_of_measurement") != unit:
        options["unit_of_measurement"] = unit
        ent_reg.async_update_entity_options(entity_id, "sensor", options)


def _reset_stale_forced_unit(
    ent_reg: er.EntityRegistry,
    coordinator: TrueNASCoordinator,
    identity: str,
    description: TrueNASSensorEntityDescription,
) -> None:
    """Undo a stale GB/GiB unit a past bug forced onto a fixed-unit description."""
    for reference, _value in _description_references(coordinator, description):
        _reset_entity_unit(ent_reg, identity, description, reference)


def _reset_entity_unit(
    ent_reg: er.EntityRegistry,
    identity: str,
    description: TrueNASSensorEntityDescription,
    reference: Any,
) -> None:
    """Clear a unit the pre-fix migration bug forced, back to the description's own unit.

    Before the GB_SCALED_UNITS scoping fix, every DATA_SIZE sensor -- including
    fixed-unit ones like app memory/block I/O -- was force-written to a
    GB/GiB-scaled unit on every startup. Since that bug no longer runs for
    these descriptions, any entity still holding a mismatched unit is a
    leftover from it; reset it and log the correction so it isn't a silent,
    permanent inconsistency for already-affected installs.
    """
    entity_id = ent_reg.async_get_entity_id(
        "sensor", DOMAIN, format_unique_id(identity, description.key, reference)
    )
    if entity_id is None:
        return

    target_unit = description.suggested_unit_of_measurement
    entry = ent_reg.async_get(entity_id)
    options = dict(entry.options.get("sensor", {})) if entry else {}
    current_unit = options.get("unit_of_measurement")
    if current_unit is None or current_unit == target_unit:
        return

    del options["unit_of_measurement"]
    ent_reg.async_update_entity_options(entity_id, "sensor", options)
    _LOGGER.info(
        "Reset %s from a stale forced unit (%s) back to %s; a prior release's "
        "unit migration incorrectly applied the GB/GiB scale to this sensor",
        entity_id,
        current_unit,
        target_unit,
    )


async def async_setup_entry(
    hass: HomeAssistant, config_entry: TrueNASConfigEntry
) -> bool:
    """Set up TrueNAS config entry."""
    coordinator = TrueNASCoordinator(hass, config_entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        await coordinator.api.close()
        raise
    config_entry.runtime_data = coordinator
    coordinator.system_device_id = register_system_device(
        hass, config_entry, coordinator
    )

    _migrate_data_size_units(hass, config_entry, coordinator)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Re-discover entities on every refresh (new interface/pool/dataset) without a reload.
    @callback
    def _handle_coordinator_refresh() -> None:
        async_dispatcher_send(hass, SIGNAL_UPDATE_SENSORS, coordinator)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_handle_coordinator_refresh)
    )

    return True


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
