"""Entity registry migration helpers for the BLANCO integration."""

from __future__ import annotations

import logging

from blanco_smart_home_api_client import BlancoLogLevel, blanco_log

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .const import (
    CONF_BACKFILL_DONE,
    CONF_LAST_ACTION_TS,
    CONF_STATS_MIGRATED,
    CONF_WATER_TOTALS_ML,
)

_LOGGER = logging.getLogger(__name__)

# Sensor unique_id suffixes whose unit may have been cached as mL in the
# entity registry by earlier versions of the integration.
_STALE_ML_SENSOR_KEYS: frozenset[str] = frozenset(
    {
        "_water_total",
        "_water_still",
        "_water_medium",
        "_water_classic",
        "_water_hot",
        "_last_dispensing",
    }
)


def migrate_sensor_units(hass: HomeAssistant, entry_id: str) -> None:
    """Clear stale mL unit overrides from water sensor entities in the registry.

    Earlier versions of the integration registered water sensors with
    native_unit_of_measurement=MILLILITERS.  HA cached this in the entity
    registry in two places that both take precedence over the sensor's
    reported native unit:

      1. entity_entry.unit_of_measurement  — direct display-unit override
      2. entity_entry.options["sensor.private"]["suggested_unit_of_measurement"]
         — HA's internal cache of the unit at first registration; HA uses this
           to restore unit_of_measurement after it is cleared, so both fields
           must be removed together.
    """
    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry_id):
        if not any(
            entity_entry.unique_id.endswith(key) for key in _STALE_ML_SENSOR_KEYS
        ):
            continue
        # Check whether either storage location contains a stale mL value.
        direct_unit = entity_entry.unit_of_measurement
        private_opts = entity_entry.options.get("sensor.private", {})
        suggested_unit = private_opts.get("suggested_unit_of_measurement")
        if direct_unit != "mL" and suggested_unit != "mL":
            continue
        # Clear the direct unit override.
        registry.async_update_entity(entity_entry.entity_id, unit_of_measurement=None)
        # Clear the cached suggested unit so HA does not restore the mL override
        # on the next startup.
        registry.async_update_entity_options(
            entity_entry.entity_id, "sensor.private", None
        )
        blanco_log(
            _LOGGER,
            BlancoLogLevel.INFO,
            "Cleared stale mL unit override for entity %s",
            entity_entry.entity_id,
        )


def migrate_entity_ids(
    hass: HomeAssistant,
    entry_id: str,
    dev_id: str,
    serial: str,
) -> None:
    """Rename entity IDs generated from translated names to stable English keys.

    On HA instances configured with a language included in NATIVE_ENTITY_IDS
    (e.g. German), entity IDs are derived from translated names rather than
    stable English translation keys.  This migration renames any such entities
    to the canonical form '{platform}.blanco_{serial_slug}_{description_key}'.

    The canonical form is also an improvement over the previous dev_id-based
    format (e.g. ``sensor.abc123devid_co2_rest``) because the serial number is
    short, human-readable, and consistent across reinstalls.
    """
    if not dev_id or not serial:
        return

    serial_slug = slugify(serial)
    unique_id_prefix = f"{dev_id}_"

    registry = er.async_get(hass)
    for entity_entry in er.async_entries_for_config_entry(registry, entry_id):
        if not entity_entry.unique_id.startswith(unique_id_prefix):
            continue
        key = entity_entry.unique_id[len(unique_id_prefix) :]
        platform = entity_entry.domain  # "sensor" or "binary_sensor"
        expected_entity_id = f"{platform}.blanco_{serial_slug}_{key}"
        if entity_entry.entity_id == expected_entity_id:
            continue
        blanco_log(
            _LOGGER,
            BlancoLogLevel.INFO,
            "Migrating entity ID: %s → %s",
            entity_entry.entity_id,
            expected_entity_id,
        )
        registry.async_update_entity(
            entity_entry.entity_id, new_entity_id=expected_entity_id
        )


def migrate_statistic_ids(hass: HomeAssistant, entry_id: str) -> None:
    """Reset CONF_BACKFILL_DONE so coordinator re-backfills under serial-based stat IDs.

    Earlier versions used _stat_id_part(dev_id) which produced an unreadable
    SHA-256-derived slug (e.g. ``blanco:2b650b8e..._water_all``).  The new
    format uses _stat_id_part(serial) so statistic IDs are human-readable and
    consistent with entity IDs (e.g. ``blanco:25c2211_63595_water_all``).
    Resetting the backfill flag causes the coordinator to re-fetch all
    historical events and write them under the new serial-based IDs.
    """
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.data.get(CONF_STATS_MIGRATED):
        return
    # Reset the backfill state completely so the coordinator re-processes all
    # historical events and writes statistics under the new serial-based IDs.
    # CONF_LAST_ACTION_TS must be reset to 0 alongside CONF_BACKFILL_DONE, because
    # _update_water_totals filters events by evt_ts > _last_action_ts — leaving the
    # old timestamp in place would cause the re-backfill to produce zero stat points.
    # CONF_WATER_TOTALS_ML is also cleared so that the running totals are rebuilt
    # from scratch and remain consistent with the re-imported statistics.
    hass.config_entries.async_update_entry(
        entry,
        data={
            **entry.data,
            CONF_BACKFILL_DONE: False,
            CONF_LAST_ACTION_TS: 0,
            CONF_WATER_TOTALS_ML: {},
            CONF_STATS_MIGRATED: True,
        },
    )
    blanco_log(
        _LOGGER,
        BlancoLogLevel.INFO,
        "Statistic ID migration: backfill state reset; "
        "coordinator will re-backfill under serial-based statistic IDs",
    )
