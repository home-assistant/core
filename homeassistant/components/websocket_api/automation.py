"""Automation related helper methods for the Websocket API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
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
from homeassistant.util.hass_dict import HassKey

_LOGGER = logging.getLogger(__name__)

FLATTENED_SERVICE_DESCRIPTIONS_CACHE: HassKey[
    tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]
] = HassKey("websocket_automation_flat_service_description_cache")

AUTOMATION_COMPONENT_LOOKUP_CACHE: HassKey[
    dict[
        AutomationComponentType,
        tuple[Mapping[str, Any], _AutomationComponentLookupTable],
    ]
] = HassKey("websocket_automation_component_lookup_cache")


class AutomationComponentType(StrEnum):
    """Types of automation components."""

    TRIGGERS = "triggers"
    CONDITIONS = "conditions"
    SERVICES = "services"


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


@dataclass(slots=True, kw_only=True)
class _AutomationComponentLookupTable:
    """Helper class for looking up automation components."""

    domain_components: dict[str | None, list[_AutomationComponentLookupData]]
    component_count: int


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


def _get_automation_component_lookup_table(
    hass: HomeAssistant,
    component_type: AutomationComponentType,
    component_descriptions: Mapping[str, Mapping[str, Any] | None],
) -> _AutomationComponentLookupTable:
    """Get a dict of automation components keyed by domain, along with the total number of components.

    Returns a cached object if available.
    """

    try:
        cache = hass.data[AUTOMATION_COMPONENT_LOOKUP_CACHE]
    except KeyError:
        cache = hass.data[AUTOMATION_COMPONENT_LOOKUP_CACHE] = {}

    if (cached := cache.get(component_type)) is not None:
        cached_descriptions, cached_lookup = cached
        if cached_descriptions is component_descriptions:
            return cached_lookup

    _LOGGER.debug(
        "Automation component lookup data for %s has no cache yet", component_type
    )

    lookup_table = _AutomationComponentLookupTable(
        domain_components={}, component_count=0
    )
    for component, description in component_descriptions.items():
        if description is None or CONF_TARGET not in description:
            _LOGGER.debug("Skipping component %s without target description", component)
            continue
        domains = _get_automation_component_domains(description[CONF_TARGET])
        lookup_data = _AutomationComponentLookupData.create(
            component, description[CONF_TARGET]
        )
        for domain in domains:
            lookup_table.domain_components.setdefault(domain, []).append(lookup_data)
        lookup_table.component_count += 1

    cache[component_type] = (component_descriptions, lookup_table)
    return lookup_table


def _async_get_automation_components_for_target(
    hass: HomeAssistant,
    component_type: AutomationComponentType,
    target_selection: ConfigType,
    expand_group: bool,
    component_descriptions: Mapping[str, Mapping[str, Any] | None],
) -> set[str]:
    """Get automation components (triggers/conditions/services) for a target.

    Returns all components that can be used on any entity that are currently part of a target.
    """
    extracted = target_helpers.async_extract_referenced_entity_ids(
        hass,
        target_helpers.TargetSelection(target_selection),
        expand_group=expand_group,
    )
    _LOGGER.debug("Extracted entities for lookup: %s", extracted)

    lookup_table = _get_automation_component_lookup_table(
        hass, component_type, component_descriptions
    )
    _LOGGER.debug(
        "Automation components per domain: %s", lookup_table.domain_components
    )

    entity_infos = entity_sources(hass)
    matched_components: set[str] = set()
    for entity_id in extracted.referenced | extracted.indirectly_referenced:
        if lookup_table.component_count == len(matched_components):
            # All automation components matched already, so we don't need to iterate further
            break

        entity_info = entity_infos.get(entity_id)
        if entity_info is None:
            _LOGGER.debug("No entity source found for %s", entity_id)
            continue

        entity_domain = entity_id.split(".")[0]
        entity_integration = entity_info["domain"]
        for domain in (entity_domain, entity_integration, None):
            if not (
                domain_component_data := lookup_table.domain_components.get(domain)
            ):
                continue
            for component_data in domain_component_data:
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
        hass,
        AutomationComponentType.TRIGGERS,
        target_selector,
        expand_group,
        descriptions,
    )


async def async_get_conditions_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get conditions for a target."""
    descriptions = await async_get_all_condition_descriptions(hass)
    return _async_get_automation_components_for_target(
        hass,
        AutomationComponentType.CONDITIONS,
        target_selector,
        expand_group,
        descriptions,
    )


async def async_get_services_for_target(
    hass: HomeAssistant, target_selector: ConfigType, expand_group: bool
) -> set[str]:
    """Get services for a target."""
    descriptions = await async_get_all_service_descriptions(hass)

    def get_flattened_service_descriptions() -> dict[str, dict[str, Any]]:
        """Get flattened service descriptions, with caching."""
        if FLATTENED_SERVICE_DESCRIPTIONS_CACHE in hass.data:
            cached_descriptions, cached_flattened_descriptions = hass.data[
                FLATTENED_SERVICE_DESCRIPTIONS_CACHE
            ]
            # If the descriptions are the same, return the cached flattened version
            if cached_descriptions is descriptions:
                return cached_flattened_descriptions

        # Flatten dicts to be keyed by domain.name to match trigger/condition format
        flattened_descriptions = {
            f"{domain}.{service_name}": desc
            for domain, services in descriptions.items()
            for service_name, desc in services.items()
        }
        hass.data[FLATTENED_SERVICE_DESCRIPTIONS_CACHE] = (
            descriptions,
            flattened_descriptions,
        )
        return flattened_descriptions

    return _async_get_automation_components_for_target(
        hass,
        AutomationComponentType.SERVICES,
        target_selector,
        expand_group,
        get_flattened_service_descriptions(),
    )
