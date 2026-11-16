"""Deprecation helpers for the DoorBird integration."""

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

DEPRECATED_REMOVAL_VERSION = "2027.5.0"
EVENTS_DOCS_URL = "https://www.home-assistant.io/integrations/doorbird/#events"


@callback
def async_should_create_deprecated_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    *,
    config_entry_id: str,
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
) -> bool:
    """Return whether a deprecated entity should still be created.

    Raises the repair issue while the user has the entity and removes it once
    the user disables it. Only runs during platform setup, so that takes a reload.
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
        # Disabling the device also disables the entity, which is not a request
        # to remove it.
        if entity_entry.disabled_by is er.RegistryEntryDisabler.USER:
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
        config_entry_id=config_entry_id,
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
    items: list[str] = []
    for integration, entities in (
        ("automation", automations_with_entity(hass, entity_id)),
        ("script", scripts_with_entity(hass, entity_id)),
    ):
        for used_entity_id in entities:
            # YAML automations without an id have no registry entry to link to.
            if item := entity_registry.async_get(used_entity_id):
                items.append(
                    f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
                )
            else:
                items.append(f"- `{used_entity_id}`")
    return items
