"""Automation related helper methods for the Websocket API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.const import CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import target as target_helpers
from homeassistant.helpers.entity import (
    entity_sources,
    get_device_class,
    get_supported_features,
)
from homeassistant.helpers.service import (
    async_get_all_descriptions as async_get_all_service_descriptions,
)
from homeassistant.helpers.trigger import (
    async_get_all_descriptions as async_get_all_trigger_descriptions,
)
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True, kw_only=True)
class _EntityFilter:
    """Single entity filter configuration with AND logic for criteria."""

    domains: set[str]
    device_classes: set[str]
    supported_features: set[int]

    def matches(self, hass: HomeAssistant, entity_id: str, domain: str) -> bool:
        """Return if entity matches all criteria in this filter."""
        if self.domains and domain not in self.domains:
            return False

        if self.device_classes:
            entity_device_class = get_device_class(hass, entity_id)
            if (
                entity_device_class is None
                or entity_device_class not in self.device_classes
            ):
                return False

        if self.supported_features:
            entity_supported_features = get_supported_features(hass, entity_id)
            if not any(
                feature & entity_supported_features
                for feature in self.supported_features
            ):
                return False

        return True


@dataclass(slots=True, kw_only=True)
class _ComponentLookupData:
    """Helper class for looking up automation components."""

    component: str
    filters: list[_EntityFilter]

    def matches(self, hass: HomeAssistant, entity_id: str, domain: str) -> bool:
        """Return if entity matches ANY of the filters."""
        if not self.filters:
            return True
        return any(f.matches(hass, entity_id, domain) for f in self.filters)


def _build_component_lookup_data(
    component: str, target_description: dict[str, Any]
) -> _ComponentLookupData:
    """Build automation component lookup data from target description."""
    filters: list[_EntityFilter] = []

    entity_filters_config = target_description.get("entity", [])
    for entity_filter_config in entity_filters_config:
        entity_filter = _EntityFilter(
            domains=set(entity_filter_config.get("domain", [])),
            device_classes=set(entity_filter_config.get("device_class", [])),
            supported_features=set(entity_filter_config.get("supported_features", [])),
        )
        filters.append(entity_filter)

    return _ComponentLookupData(
        component=component,
        filters=filters,
    )


async def _async_get_components_for_target(
    hass: HomeAssistant,
    target_selector: ConfigType,
    expand_group: bool,
    descriptions: dict[str, dict[str, Any] | None],
) -> set[str]:
    """Get automation components (triggers/conditions/services) for a target.

    Returns all components that can be used on any entity that are currently part of a target.
    """
    selector_data = target_helpers.TargetSelectorData(target_selector)
    extracted = target_helpers.async_extract_referenced_entity_ids(
        hass, selector_data, expand_group=expand_group
    )
    _LOGGER.debug("Extracted entities for lookup: %s", extracted)

    # Build lookup structure: domain -> list of trigger/condition/service lookup data
    domain_components: dict[str, list[_ComponentLookupData]] = {}
    component_count = 0
    for component, description in descriptions.items():
        if description is None or CONF_TARGET not in description:
            _LOGGER.debug("Skipping component %s without target description", component)
            continue
        domain = component.split(".")[0]
        domain_components.setdefault(domain, []).append(
            _build_component_lookup_data(component, description[CONF_TARGET])
        )
        component_count += 1

    _LOGGER.debug("Domain components: %s", domain_components)

    entity_infos = entity_sources(hass)
    matched_components: set[str] = set()
    for entity_id in extracted.referenced | extracted.indirectly_referenced:
        if component_count == len(matched_components):
            break

        entity_info = entity_infos.get(entity_id)
        if entity_info is None:
            _LOGGER.warning("No entity source found for %s", entity_id)
            continue

        entity_domain = entity_id.split(".")[0]
        for domain in (entity_domain, entity_info["domain"]):
            for component_data in domain_components.get(domain, []):
                if component_data.component in matched_components:
                    continue
                if component_data.matches(hass, entity_id, entity_domain):
                    matched_components.add(component_data.component)

    return matched_components


async def async_get_triggers_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get triggers for a target."""
    descriptions = await async_get_all_trigger_descriptions(hass)
    return await _async_get_components_for_target(
        hass, target_selector, expand_group, descriptions
    )


async def async_get_services_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get services for a target."""
    descriptions = await async_get_all_service_descriptions(hass)
    # Flatten domain+name to match trigger/condition format
    descriptions_flatten = {
        f"{domain}.{service_name}": desc
        for domain, services in descriptions.items()
        for service_name, desc in services.items()
    }
    return await _async_get_components_for_target(
        hass, target_selector, expand_group, descriptions_flatten
    )
