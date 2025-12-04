"""Automation related helper methods for the Websocket API."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Self

from homeassistant.const import CONF_TARGET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import target as target_helpers
from homeassistant.helpers.condition import (
    async_get_all_descriptions as async_get_all_condition_descriptions,
)
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
    """Single entity filter configuration."""

    integration: str | None
    domains: set[str]
    device_classes: set[str]
    supported_features: set[int]

    def matches(
        self, hass: HomeAssistant, entity_id: str, domain: str, integration: str
    ) -> bool:
        """Return if entity matches all criteria in this filter."""
        if self.integration and integration != self.integration:
            return False

        if self.domains and domain not in self.domains:
            return False

        if self.device_classes:
            if (
                entity_device_class := get_device_class(hass, entity_id)
            ) is None or entity_device_class not in self.device_classes:
                return False

        if self.supported_features:
            entity_supported_features = get_supported_features(hass, entity_id)
            if not any(
                feature & entity_supported_features == feature
                for feature in self.supported_features
            ):
                return False

        return True


@dataclass(slots=True, kw_only=True)
class _AutomationComponentLookupData:
    """Helper class for looking up automation components."""

    component: str
    filters: list[_EntityFilter]

    @classmethod
    def create(cls, component: str, target_description: dict[str, Any]) -> Self:
        """Build automation component lookup data from target description."""
        filters: list[_EntityFilter] = []

        entity_filters_config = target_description.get("entity", [])
        for entity_filter_config in entity_filters_config:
            entity_filter = _EntityFilter(
                integration=entity_filter_config.get("integration"),
                domains=set(entity_filter_config.get("domain", [])),
                device_classes=set(entity_filter_config.get("device_class", [])),
                supported_features=set(
                    entity_filter_config.get("supported_features", [])
                ),
            )
            filters.append(entity_filter)

        return cls(component=component, filters=filters)

    def matches(
        self, hass: HomeAssistant, entity_id: str, domain: str, integration: str
    ) -> bool:
        """Return if entity matches ANY of the filters."""
        if not self.filters:
            return True
        return any(
            f.matches(hass, entity_id, domain, integration) for f in self.filters
        )


def _get_automation_component_domains(
    target_description: dict[str, Any],
) -> set[str | None]:
    """Get a list of domains (including integration domains) of an automation component.

    The list of domains is extracted from each target's entity filters.
    If a filter is missing both domain and integration keys, None is added to the
    returned set.
    """
    entity_filters_config = target_description.get("entity", [])
    if not entity_filters_config:
        return {None}

    domains: set[str | None] = set()
    for entity_filter_config in entity_filters_config:
        filter_integration = entity_filter_config.get("integration")
        filter_domains = entity_filter_config.get("domain", [])

        if not filter_domains and not filter_integration:
            domains.add(None)
            continue

        if filter_integration:
            domains.add(filter_integration)

        for domain in filter_domains:
            domains.add(domain)

    return domains


def _async_get_automation_components_for_target(
    hass: HomeAssistant,
    target_selection: ConfigType,
    expand_group: bool,
    component_descriptions: dict[str, dict[str, Any] | None],
) -> set[str]:
    """Get automation components (triggers/conditions/services) for a target.

    Returns all components that can be used on any entity that are currently part of a target.
    """
    extracted = target_helpers.async_extract_referenced_entity_ids(
        hass,
        target_helpers.TargetSelectorData(target_selection),
        expand_group=expand_group,
    )
    _LOGGER.debug("Extracted entities for lookup: %s", extracted)

    # Build lookup structure: domain -> list of trigger/condition/service lookup data
    domain_components: dict[str | None, list[_AutomationComponentLookupData]] = {}
    component_count = 0
    for component, description in component_descriptions.items():
        if description is None or CONF_TARGET not in description:
            _LOGGER.debug("Skipping component %s without target description", component)
            continue
        domains = _get_automation_component_domains(description[CONF_TARGET])
        lookup_data = _AutomationComponentLookupData.create(
            component, description[CONF_TARGET]
        )
        for domain in domains:
            domain_components.setdefault(domain, []).append(lookup_data)
        component_count += 1

    _LOGGER.debug("Automation components per domain: %s", domain_components)

    entity_infos = entity_sources(hass)
    matched_components: set[str] = set()
    for entity_id in extracted.referenced | extracted.indirectly_referenced:
        if component_count == len(matched_components):
            # All automation components matched already, so we don't need to iterate further
            break

        entity_info = entity_infos.get(entity_id)
        if entity_info is None:
            _LOGGER.debug("No entity source found for %s", entity_id)
            continue

        entity_domain = entity_id.split(".")[0]
        entity_integration = entity_info["domain"]
        for domain in (entity_domain, entity_integration, None):
            for component_data in domain_components.get(domain, []):
                if component_data.component in matched_components:
                    continue
                if component_data.matches(
                    hass, entity_id, entity_domain, entity_integration
                ):
                    matched_components.add(component_data.component)

    return matched_components


async def async_get_triggers_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get triggers for a target."""
    descriptions = await async_get_all_trigger_descriptions(hass)
    return _async_get_automation_components_for_target(
        hass, target_selector, expand_group, descriptions
    )


async def async_get_conditions_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get conditions for a target."""
    descriptions = await async_get_all_condition_descriptions(hass)
    return _async_get_automation_components_for_target(
        hass, target_selector, expand_group, descriptions
    )


async def async_get_services_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get services for a target."""
    descriptions = await async_get_all_service_descriptions(hass)
    # Flatten dicts to be keyed by domain.name to match trigger/condition format
    descriptions_flatten = {
        f"{domain}.{service_name}": desc
        for domain, services in descriptions.items()
        for service_name, desc in services.items()
    }
    return _async_get_automation_components_for_target(
        hass, target_selector, expand_group, descriptions_flatten
    )
