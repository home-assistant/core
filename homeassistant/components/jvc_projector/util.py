"""Utility helpers for the jvc_projector integration."""

from __future__ import annotations

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN


def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    issue_string: str,
    replacement_entity_unique_id: str,
    replacement_entity_id: str,
    version: str = "2026.9.0",
) -> bool:
    """Create an issue for deprecated entities."""
    if entity_id := entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    ):
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
                    Platform.SELECT, DOMAIN, replacement_entity_unique_id
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

    async_delete_issue(hass, DOMAIN, issue_id)
    return False


def get_automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> list[str]:
    """Get automations and scripts using an entity."""
    # These helpers return referencing automation/script entity IDs.
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
            # Prefer entity-registry metadata so we can render edit links.
            if item := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
                )
            else:
                # Keep unresolved references as plain text so they still count as usage.
                items.append(f"- `{used_entity_id}`")

    return items
