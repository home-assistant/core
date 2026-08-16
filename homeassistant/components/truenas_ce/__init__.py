"""The TrueNAS integration."""

from logging import getLogger
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
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
from .entity import format_unique_id, register_system_device
from .helper import scaled_data_unit
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
