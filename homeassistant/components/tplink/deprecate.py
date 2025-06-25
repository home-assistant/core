"""Helper class for deprecating entities."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kasa import Device

from homeassistant.components.automation import automations_with_entity
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.script import scripts_with_entity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from . import legacy_device_id
from .const import DOMAIN

if TYPE_CHECKING:
    from .entity import CoordinatedTPLinkEntity, TPLinkEntityDescription


@dataclass(slots=True)
class DeprecatedInfo:
    """Class to define deprecation info for deprecated entities."""

    platform: str
    new_platform: str
    breaks_in_ha_version: str


def async_check_create_deprecated(
    hass: HomeAssistant,
    unique_id: str,
    entity_description: TPLinkEntityDescription,
) -> bool:
    """Return true if the entity should be created based on the deprecated_info.

    If deprecated_info is not defined will return true.
    If entity not yet created will return false.
    If entity disabled will return false.
    """
    if not entity_description.deprecated_info:
        return True

    deprecated_info = entity_description.deprecated_info
    platform = deprecated_info.platform

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id(
        platform,
        DOMAIN,
        unique_id,
    )
    if not entity_id:
        return False

    entity_entry = ent_reg.async_get(entity_id)
    assert entity_entry
    return not entity_entry.disabled


def async_process_deprecated(
    hass: HomeAssistant,
    platform_domain: str,
    entry_id: str,
    entities: Sequence[CoordinatedTPLinkEntity],
    device: Device,
) -> None:
    """Process deprecated entities for a device.

    Create issues for deprececated entities that appear in automations.
    Delete entities that are no longer provided by the integration either
    because they have been removed at the end of the deprecation period, or
    they are disabled by the user so the async_check_create_deprecated
    returned false.
    """
    ent_reg = er.async_get(hass)
    for entity in entities:
        if not (deprecated_info := entity.entity_description.deprecated_info):
            continue

        assert entity.unique_id
        entity_id = ent_reg.async_get_entity_id(
            platform_domain,
            DOMAIN,
            entity.unique_id,
        )
        assert entity_id
        # Check for issues that need to be created
        entity_automations = automations_with_entity(hass, entity_id)
        entity_scripts = scripts_with_entity(hass, entity_id)

        for item in entity_automations + entity_scripts:
            async_create_issue(
                hass,
                DOMAIN,
                f"deprecated_entity_{entity_id}_{item}",
                breaks_in_ha_version=deprecated_info.breaks_in_ha_version,
                is_fixable=False,
                is_persistent=False,
                severity=IssueSeverity.WARNING,
                translation_key="deprecated_entity",
                translation_placeholders={
                    "entity": entity_id,
                    "info": item,
                    "platform": platform_domain,
                    "new_platform": deprecated_info.new_platform,
                },
            )

    # The light platform does not currently support cleaning up disabled
    # deprecated entities because it uses two entity classes so a completeness
    # check is not possible. It also uses the mac address as device id in some
    # instances instead of device_id.
    if platform_domain == LIGHT_DOMAIN:
        return

    # Remove entities that are no longer provided and have been disabled.
    device_id = legacy_device_id(device)

    unique_ids = {entity.unique_id for entity in entities}
    for entity_entry in er.async_entries_for_config_entry(ent_reg, entry_id):
        if (
            entity_entry.domain == platform_domain
            and entity_entry.disabled
            and entity_entry.unique_id.startswith(device_id)
            and entity_entry.unique_id not in unique_ids
        ):
            ent_reg.async_remove(entity_entry.entity_id)
            continue
