"""Define RainMachine utilities."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN, LOGGER


class RunStates(StrEnum):
    """Define an enum for program/zone run states."""

    NOT_RUNNING = "Not Running"
    QUEUED = "Queued"
    RUNNING = "Running"


RUN_STATE_MAP = {
    0: RunStates.NOT_RUNNING,
    1: RunStates.RUNNING,
    2: RunStates.QUEUED,
}


@dataclass
class EntityDomainReplacementStrategy:
    """Define an entity replacement."""

    old_domain: str
    old_unique_id: str
    replacement_entity_id: str
    breaks_in_ha_version: str
    remove_old_entity: bool = True


@callback
def async_finish_entity_domain_replacements(
    hass: HomeAssistant,
    entry: ConfigEntry,
    entity_replacement_strategies: Iterable[EntityDomainReplacementStrategy],
) -> None:
    """Remove old entities and create a repairs issue with info on their replacement."""
    ent_reg = er.async_get(hass)
    for strategy in entity_replacement_strategies:
        try:
            [registry_entry] = [
                registry_entry
                for registry_entry in ent_reg.entities.get_entries_for_config_entry_id(
                    entry.entry_id
                )
                if registry_entry.domain == strategy.old_domain
                and registry_entry.unique_id == strategy.old_unique_id
            ]
        except ValueError:
            continue

        old_entity_id = registry_entry.entity_id
        if strategy.remove_old_entity:
            LOGGER.debug('Removing old entity: "%s"', old_entity_id)
            ent_reg.async_remove(old_entity_id)


def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform_domain: Platform,
    entity_unique_id: str,
    issue_id: str,
    issue_string: str,
    replacement_platform_domain: Platform,
    replacement_entity_unique_id: str,
    replacement_entity_id: str,
    version: str,
) -> bool:
    """Create an issue for a deprecated entity that has a replacement."""
    if not (
        entity_id := entity_registry.async_get_entity_id(
            platform_domain, DOMAIN, entity_unique_id
        )
    ):
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    entity_entry = entity_registry.async_get(entity_id)
    if not entity_entry:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    items = get_automations_and_scripts_using_entity(hass, entity_id)
    if entity_entry.disabled and not items:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    translation_key = issue_string
    placeholders = {
        "entity_id": entity_id,
        "entity_name": entity_entry.name or entity_entry.original_name or "Unknown",
        "replacement_entity_id": (
            entity_registry.async_get_entity_id(
                replacement_platform_domain, DOMAIN, replacement_entity_unique_id
            )
            or replacement_entity_id
        ),
    }
    if items:
        translation_key = f"{translation_key}_scripts"
        placeholders["items"] = "\n".join(items)

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=version,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )
    return True


def get_automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> list[str]:
    """Get automations and scripts using an entity."""
    automations = automations_with_entity(hass, entity_id)
    scripts = scripts_with_entity(hass, entity_id)
    if not automations and not scripts:
        return []

    entity_registry = er.async_get(hass)
    items: list[str] = []
    for integration, entities in (
        ("automation", automations),
        ("script", scripts),
    ):
        for used_entity_id in entities:
            if item := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
                )
            else:
                items.append(f"- `{used_entity_id}`")

    return items


def key_exists(data: dict[str, Any], search_key: str) -> bool:
    """Return whether a key exists in a nested dict."""
    for key, value in data.items():
        if key == search_key:
            return True
        if isinstance(value, dict):
            return key_exists(value, search_key)
    return False
