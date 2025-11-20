"""Commands part of Websocket API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, target as target_helpers
from homeassistant.helpers.trigger import (
    async_get_all_descriptions as async_get_all_trigger_descriptions,
)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class TriggerLookupData:
    """Data structure for looking up triggers."""

    trigger: str
    domains: set[str]
    device_classes: set[str]
    supported_features: list[int]

    def matches(self, entity_entry: er.RegistryEntry) -> bool:
        """Return if entity matches the filters."""
        if self.domains and entity_entry.domain not in self.domains:
            return False
        if self.device_classes:
            entity_device_class = entity_entry.device_class
            if (
                entity_device_class is None
                or entity_device_class not in self.device_classes
            ):
                return False
        if self.supported_features:
            entity_supported_features = entity_entry.supported_features
            if entity_supported_features is None or not any(
                feature & entity_supported_features
                for feature in self.supported_features
            ):
                return False
        return True


def _build_trigger_lookup_data(
    trigger: str, target_description: dict[str, Any]
) -> TriggerLookupData:
    """Build trigger lookup data from target description."""
    domains: set[str] = set()
    device_classes: set[str] = set()
    supported_features: list[int] = []

    selector_entities = target_description.get("entity", [])
    for selector_entity in selector_entities:
        domains.update(selector_entity.get("domain", []))
        device_classes.update(selector_entity.get("device_class", []))
        supported_features.extend(selector_entity.get("supported_features", []))

    return TriggerLookupData(
        trigger=trigger,
        domains=domains,
        device_classes=device_classes,
        supported_features=supported_features,
    )


async def async_get_triggers_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get triggers for target command.

    This command returns all triggers that can be used on any entity that are currently
    part of a target.
    """
    selector_data = target_helpers.TargetSelectorData(target_selector)
    extracted = target_helpers.async_extract_referenced_entity_ids(
        hass, selector_data, expand_group=expand_group
    )
    _LOGGER.debug("Extracted entities for trigger lookup: %s", extracted)

    descriptions = await async_get_all_trigger_descriptions(hass)

    # Build lookup structure: domain -> list of trigger lookup data
    domain_triggers: dict[str, list[TriggerLookupData]] = {}
    trigger_count = 0
    for trigger, description in descriptions.items():
        if description is None or CONF_TARGET not in description:
            _LOGGER.debug("Skipping trigger %s without target description", trigger)
            continue
        domain = trigger.split(".")[0]
        domain_triggers.setdefault(domain, []).append(
            _build_trigger_lookup_data(trigger, description[CONF_TARGET])
        )
        trigger_count += 1

    _LOGGER.debug("Domain triggers: %s", domain_triggers)

    matched_triggers: set[str] = set()

    entity_registry = er.async_get(hass)
    for entity_id in extracted.referenced.union(extracted.indirectly_referenced):
        if trigger_count == len(matched_triggers):
            break

        if (entity_entry := entity_registry.async_get(entity_id)) is None:
            continue

        for domain in (entity_entry.domain, entity_entry.platform):
            for trigger_data in domain_triggers.get(domain, []):
                if trigger_data.trigger in matched_triggers:
                    continue
                if trigger_data.matches(entity_entry):
                    matched_triggers.add(trigger_data.trigger)

    return matched_triggers
