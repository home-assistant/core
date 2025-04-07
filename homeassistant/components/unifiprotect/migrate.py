"""UniFi Protect data migrations."""

from __future__ import annotations

from itertools import chain
import logging
from typing import TypedDict

from uiprotect import ProtectApiClient
from uiprotect.data import Bootstrap

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.helpers.issue_registry import IssueSeverity

from .const import DOMAIN
from .data import UFPConfigEntry

_LOGGER = logging.getLogger(__name__)


class EntityRef(TypedDict):
    """Entity ref parameter variable."""

    id: str
    platform: Platform


class EntityUsage(TypedDict):
    """Entity usages response variable."""

    automations: dict[str, list[str]]
    scripts: dict[str, list[str]]


@callback
def check_if_used(
    hass: HomeAssistant, entry: UFPConfigEntry, entities: dict[str, EntityRef]
) -> dict[str, EntityUsage]:
    """Check for usages of entities and return them."""

    entity_registry = er.async_get(hass)
    refs: dict[str, EntityUsage] = {
        ref: {"automations": {}, "scripts": {}} for ref in entities
    }

    for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
        for ref_id, ref in entities.items():
            if (
                entity.domain == ref["platform"]
                and entity.disabled_by is None
                and ref["id"] in entity.unique_id
            ):
                entity_automations = automations_with_entity(hass, entity.entity_id)
                entity_scripts = scripts_with_entity(hass, entity.entity_id)
                if entity_automations:
                    refs[ref_id]["automations"][entity.entity_id] = entity_automations
                if entity_scripts:
                    refs[ref_id]["scripts"][entity.entity_id] = entity_scripts

    return refs


@callback
def create_repair_if_used(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    breaks_in: str,
    entities: dict[str, EntityRef],
) -> None:
    """Create repairs for used entities that are deprecated."""

    usages = check_if_used(hass, entry, entities)
    for ref_id, refs in usages.items():
        issue_id = f"deprecate_{ref_id}"
        automations = refs["automations"]
        scripts = refs["scripts"]
        if automations or scripts:
            items = sorted(
                set(chain.from_iterable(chain(automations.values(), scripts.values())))
            )
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                breaks_in_ha_version=breaks_in,
                severity=IssueSeverity.WARNING,
                translation_key=issue_id,
                translation_placeholders={
                    "items": "* `" + "`\n* `".join(items) + "`\n"
                },
            )
        else:
            _LOGGER.debug("No found usages of %s", ref_id)
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_migrate_data(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    protect: ProtectApiClient,
    bootstrap: Bootstrap,
) -> None:
    """Run all valid UniFi Protect data migrations."""

    _LOGGER.debug("Start Migrate: async_deprecate_hdr")
    async_deprecate_hdr(hass, entry)
    _LOGGER.debug("Completed Migrate: async_deprecate_hdr")


@callback
def async_deprecate_hdr(hass: HomeAssistant, entry: UFPConfigEntry) -> None:
    """Check for usages of hdr_mode switch and raise repair if it is used.

    UniFi Protect v3.0.22 changed how HDR works so it is no longer a simple on/off toggle. There is
    Always On, Always Off and Auto. So it has been migrated to a select. The old switch is now deprecated.

    Added in 2024.4.0
    """

    create_repair_if_used(
        hass,
        entry,
        "2024.10.0",
        {"hdr_switch": {"id": "hdr_mode", "platform": Platform.SWITCH}},
    )
