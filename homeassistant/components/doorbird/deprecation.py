"""Deprecation helpers for the DoorBird integration."""

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

DEPRECATED_REMOVAL_VERSION = "2027.5.0"
EVENTS_DOCS_URL = "https://www.home-assistant.io/integrations/doorbird/#events"


def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
) -> bool:
    """Handle a deprecated entity, returning whether it should still be created.

    Only runs during platform setup, so removing a disabled entity takes a reload.
    """
    entity_id = entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    )
    if (
        entity_id is None
        or (entity_entry := entity_registry.async_get(entity_id)) is None
    ):
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    if entity_entry.disabled:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    placeholders = {
        "entity_id": entity_id,
        "entity_name": entity_entry.name or entity_entry.original_name or entity_id,
        "docs_url": EVENTS_DOCS_URL,
    }
    if items := _automations_and_scripts_using_entity(hass, entity_registry, entity_id):
        translation_key = f"{translation_key}_scripts"
        placeholders["items"] = "\n".join(items)

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=DEPRECATED_REMOVAL_VERSION,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )
    return True


def _automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> list[str]:
    """Return markdown links to the automations and scripts using an entity."""
    return [
        f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
        for integration, entities in (
            ("automation", automations_with_entity(hass, entity_id)),
            ("script", scripts_with_entity(hass, entity_id)),
        )
        for used_entity_id in entities
        if (item := entity_registry.async_get(used_entity_id))
    ]
