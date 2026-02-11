"""Utility functions for SmartThings integration."""

from pysmartthings import Attribute, Capability

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from . import FullDevice
from .const import DOMAIN


def deprecate_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    platform_domain: str,
    entity_unique_id: str,
    issue_string: str,
    version: str = "2025.10.0",
) -> bool:
    """Create an issue for deprecated entities."""
    if entity_id := entity_registry.async_get_entity_id(
        platform_domain, DOMAIN, entity_unique_id
    ):
        entity_entry = entity_registry.async_get(entity_id)
        if not entity_entry:
            return False
        if entity_entry.disabled:
            entity_registry.async_remove(entity_id)
            async_delete_issue(
                hass,
                DOMAIN,
                f"{issue_string}_{entity_id}",
            )
            return False
        translation_key = issue_string
        placeholders = {
            "entity_id": entity_id,
            "entity_name": entity_entry.name or entity_entry.original_name or "Unknown",
        }
        if items := get_automations_and_scripts_using_entity(hass, entity_id):
            translation_key = f"{translation_key}_scripts"
            placeholders.update(
                {
                    "items": "\n".join(items),
                }
            )
        async_create_issue(
            hass,
            DOMAIN,
            f"{issue_string}_{entity_id}",
            breaks_in_ha_version=version,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )
        return True
    return False


def get_automations_and_scripts_using_entity(
    hass: HomeAssistant,
    entity_id: str,
) -> list[str]:
    """Get automations and scripts using an entity."""
    automations = automations_with_entity(hass, entity_id)
    scripts = scripts_with_entity(hass, entity_id)
    if not automations and not scripts:
        return []

    entity_reg = er.async_get(hass)
    return [
        f"- [{item.original_name}](/config/{integration}/edit/{item.unique_id})"
        for integration, entities in (
            ("automation", automations),
            ("script", scripts),
        )
        for entity_id in entities
        if (item := entity_reg.async_get(entity_id))
    ]


def get_range_options_count(
    device: FullDevice, component: str, capability: Capability, attribute: Attribute
) -> int:
    """Get the number of options in a range attribute.

    This helper is intentionally non-throwing. If the underlying status payload
    is missing or malformed, it will return 0 so callers can skip creating the
    related entity instead of failing platform setup.
    """
    try:
        status = device.status
        value = status[component][capability][attribute].value
    except KeyError, TypeError, AttributeError:
        # Missing component/capability/attribute or unexpected structure
        return 0

    if not isinstance(value, dict):
        return 0

    minimum = value.get("minimum")
    maximum = value.get("maximum")
    step = value.get("step")

    if (
        not isinstance(minimum, int)
        or not isinstance(maximum, int)
        or not isinstance(step, int)
    ):
        return 0

    if step <= 0 or maximum < minimum:
        return 0

    try:
        return len(range(minimum, maximum + 1, step))
    except ValueError:
        # range() can still raise ValueError for invalid arguments
        return 0
