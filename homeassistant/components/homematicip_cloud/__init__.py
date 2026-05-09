"""Support for HomematicIP Cloud devices."""

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACCESSPOINT,
    CONF_AUTHTOKEN,
    DOMAIN,
    HMIPC_AUTHTOKEN,
    HMIPC_HAPID,
    HMIPC_NAME,
)
from .hap import HomematicIPConfigEntry, HomematicipHAP
from .migration import _match_legacy_class_name, _migrate_unique_id
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=[]): vol.All(
            cv.ensure_list,
            [
                vol.Schema(
                    {
                        vol.Optional(CONF_NAME, default=""): vol.Any(cv.string),
                        vol.Required(CONF_ACCESSPOINT): cv.string,
                        vol.Required(CONF_AUTHTOKEN): cv.string,
                    }
                )
            ],
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the HomematicIP Cloud component."""
    accesspoints = config.get(DOMAIN, [])

    for conf in accesspoints:
        if conf[CONF_ACCESSPOINT] not in {
            entry.data[HMIPC_HAPID]
            for entry in hass.config_entries.async_entries(DOMAIN)
        }:
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_IMPORT},
                    data={
                        HMIPC_HAPID: conf[CONF_ACCESSPOINT],
                        HMIPC_AUTHTOKEN: conf[CONF_AUTHTOKEN],
                        HMIPC_NAME: conf[CONF_NAME],
                    },
                )
            )

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: HomematicIPConfigEntry) -> bool:
    """Set up an access point from a config entry."""

    # 0.104 introduced config entry unique id, this makes upgrading possible
    if entry.unique_id is None:
        new_data = dict(entry.data)

        hass.config_entries.async_update_entry(
            entry, unique_id=new_data[HMIPC_HAPID], data=new_data
        )

    hap = HomematicipHAP(hass, entry)

    entry.runtime_data = hap
    if not await hap.async_setup():
        return False

    # Register on HA stop event to gracefully shutdown HomematicIP Cloud connection
    hap.reset_connection_listener = hass.bus.async_listen_once(
        EVENT_HOMEASSISTANT_STOP, hap.shutdown
    )

    # Register hap as device in registry.
    device_registry = dr.async_get(hass)

    home = hap.home
    hapname = home.label if home.label != entry.unique_id else f"Home-{home.label}"

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, home.id)},
        manufacturer="eQ-3",
        # Add the name from config entry.
        name=hapname,
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HomematicIPConfigEntry
) -> bool:
    """Unload a config entry."""
    hap = entry.runtime_data
    assert hap.reset_connection_listener is not None
    hap.reset_connection_listener()

    return await hap.async_reset()


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Migrate the config entry from version 1 to version 2."""
    if config_entry.version > 2:
        return False

    if config_entry.version == 1:
        _LOGGER.debug("Migrating HomematicIP Cloud config entry to version 2")

        # Remove obsolete entities before the bulk unique_id rewrite.
        # After rewrite, old-format patterns would no longer be matchable.
        # HomematicipAccesspointStatus* entities are always obsolete (removed
        # in firmware 2.2.12+). HomematicipBatterySensor_{hapid} entities for
        # access points are also obsolete. Those legacy access point battery
        # entities do not belong to a device registry device, unlike real
        # device battery sensors, so we can safely remove them before rewrite.
        entity_registry = er.async_get(hass)
        entries = er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        )
        for entry in entries:
            if entry.unique_id.startswith("HomematicipAccesspointStatus") or (
                entry.unique_id.startswith("HomematicipBatterySensor_")
                and entry.device_id is None
            ):
                _LOGGER.debug(
                    "Removing obsolete entity: %s (%s)",
                    entry.entity_id,
                    entry.unique_id,
                )
                entity_registry.async_remove(entry.entity_id)

        # Pre-pass: deduplicate legacy entries that would migrate to the same
        # new unique_id, and drop legacy entries whose target is already
        # occupied by a stable-format entry from a previously-aborted
        # migration. Two collision shapes are handled here:
        #
        #   a) Two or more legacy entries share the same new target id (e.g.
        #      HomematicipNotificationLight + HomematicipNotificationLightV2
        #      for the same HmIP-BSL after firmware 2.0.0, or Switch +
        #      SwitchMeasuring on a device whose capability class changed).
        #
        #   b) One legacy entry shares its target with a stable-format entry
        #      that was successfully migrated on a previous run before the
        #      run aborted on a sibling collision. async_migrate_entries
        #      commits each update individually with no rollback, so partial
        #      migration is the steady state for any user who already hit
        #      this bug at least once.
        #
        # When deduplicating pure-legacy groups, prefer the entry whose
        # legacy class name is longer — that is the more specific variant
        # (V2 over V1, Measuring over plain) and the one HA has been
        # actively binding to since the class transition.
        legacy_by_target: dict[tuple[str, str], list[er.RegistryEntry]] = {}
        stable_targets: set[tuple[str, str]] = set()
        for entry in er.async_entries_for_config_entry(
            entity_registry, config_entry.entry_id
        ):
            new_id = _migrate_unique_id(entry.unique_id)
            if new_id is None:
                # Stable-format entry — record so we can detect (b).
                stable_targets.add((entry.domain, entry.unique_id))
                continue
            legacy_by_target.setdefault((entry.domain, new_id), []).append(entry)

        for key, group in legacy_by_target.items():
            if key in stable_targets:
                # (b): stable entry already occupies the target. Drop every
                # legacy duplicate; the surviving stable entry stays put.
                for dup in group:
                    _LOGGER.warning(
                        "Removing legacy registry entry %s (%s) — its"
                        " migration target %s is already in use by a stable"
                        " entry from a previously-aborted migration",
                        dup.entity_id,
                        dup.unique_id,
                        key[1],
                    )
                    entity_registry.async_remove(dup.entity_id)
                continue
            if len(group) <= 1:
                continue
            # (a): multiple legacy entries collide on the same target.
            group.sort(
                key=lambda e: len(_match_legacy_class_name(e.unique_id) or ""),
                reverse=True,
            )
            keeper, *duplicates = group
            for dup in duplicates:
                _LOGGER.warning(
                    "Removing duplicate registry entry %s (%s) — collides"
                    " with %s on migration to %s",
                    dup.entity_id,
                    dup.unique_id,
                    keeper.entity_id,
                    key[1],
                )
                entity_registry.async_remove(dup.entity_id)

        @callback
        def _update_unique_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            new_unique_id = _migrate_unique_id(entity_entry.unique_id)
            if new_unique_id is None:
                _LOGGER.debug(
                    "Skipping unique_id %s (already stable format)",
                    entity_entry.unique_id,
                )
                return None
            _LOGGER.debug(
                "Migrating %s: %s -> %s",
                entity_entry.entity_id,
                entity_entry.unique_id,
                new_unique_id,
            )
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, config_entry.entry_id, _update_unique_id)

        hass.config_entries.async_update_entry(config_entry, version=2)
        _LOGGER.info("Migration to version 2 successful")

    return True
