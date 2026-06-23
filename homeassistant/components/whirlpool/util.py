"""Utility helpers for the Whirlpool integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import DOMAIN

# Version in which deprecated entities will be removed.
DEPRECATED_REMOVAL_VERSION = "2026.12.0"


def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform_domain: str,
    entity_unique_id: str,
    issue_id: str,
    translation_key: str,
    replacement_platform_domain: str,
    replacement_entity_unique_id: str,
    replacement_entity_id: str,
) -> bool:
    """Handle deprecation of an entity that has been replaced.

    Return True if the deprecated entity should still be set up, which is the
    case when it already exists in the entity registry and has not been disabled
    by the user. While it exists, a repair issue informs the user about the
    replacement and the removal date. Once the user disables it, it is removed
    and the issue is cleared. New installations never create the entity.
    """
    entity_id = entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    )
    if entity_id is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    entity_entry = entity_registry.async_get(entity_id)
    if entity_entry is None:
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    if entity_entry.disabled:
        entity_registry.async_remove(entity_id)
        async_delete_issue(hass, DOMAIN, issue_id)
        return False

    async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        breaks_in_ha_version=DEPRECATED_REMOVAL_VERSION,
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders={
            "entity_id": entity_id,
            "entity_name": entity_entry.name or entity_entry.original_name or entity_id,
            "replacement_entity_id": (
                entity_registry.async_get_entity_id(
                    replacement_platform_domain, DOMAIN, replacement_entity_unique_id
                )
                or replacement_entity_id
            ),
        },
    )
    return True
