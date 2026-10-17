"""Entity suggestions from KNX data sources."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN
from .base import SuggestionProvider
from .const import (
    EntitySuggestion,
    EntitySuggestionsResult,
    ProviderSuggestion,
    SuggestionFilter,
)
from .functional_blocks import FunctionalBlockSuggestionProvider

if TYPE_CHECKING:
    from ...knx_module import KNXModule

SUGGESTION_PROVIDERS: list[SuggestionProvider] = [
    FunctionalBlockSuggestionProvider(),
]


def _entity_ids_by_group_address(
    hass: HomeAssistant, knx: KNXModule
) -> dict[str, list[str]]:
    """Map group addresses to the ids of entities using them."""
    entity_registry = er.async_get(hass)
    return {
        str(group_address): [
            entity_id
            for identifier in identifiers
            if (
                entity_id := entity_registry.async_get_entity_id(
                    identifier.platform, DOMAIN, identifier.unique_id
                )
            )
            is not None
        ]
        for group_address, identifiers in knx.group_address_entities.items()
    }


def _existing_entity_ids(
    suggestion: ProviderSuggestion, entity_ids_by_group_address: dict[str, list[str]]
) -> list[str]:
    """Report entities already using the group addresses of a suggestion."""
    return sorted(
        {
            entity_id
            for platform_suggestion in suggestion["suggestions"].values()
            for group_address in platform_suggestion["matched_group_addresses"]
            for entity_id in entity_ids_by_group_address.get(
                group_address["address"], ()
            )
        }
    )


def _matches(suggestion: EntitySuggestion, suggestion_filter: SuggestionFilter) -> bool:
    """Check a suggestion against a filter."""
    if (
        suggestion_filter.platform is not None
        and suggestion_filter.platform not in suggestion["suggestions"]
    ):
        return False
    if (
        suggestion_filter.group_id is not None
        and suggestion_filter.group_id != suggestion["group_id"]
    ):
        return False
    return suggestion_filter.include_configured or not suggestion["existing_entity_ids"]


async def async_get_entity_suggestions(
    hass: HomeAssistant,
    knx: KNXModule,
    suggestion_filter: SuggestionFilter | None = None,
) -> EntitySuggestionsResult:
    """Generate entity suggestions from all providers.

    Providers generate everything they know about. Duplicate detection and
    filtering are done here so they behave the same for every source.
    Results are not windowed - a caller that has to bound its response
    applies its own limit.
    """
    suggestion_filter = suggestion_filter or SuggestionFilter()
    entity_ids_by_group_address = _entity_ids_by_group_address(hass, knx)
    result = EntitySuggestionsResult(suggestions=[], providers={})
    for provider in SUGGESTION_PROVIDERS:
        provider_result = await provider.async_get_suggestions(hass, knx)
        result["providers"][provider.provider_id] = provider_result["hints"]
        for provider_suggestion in provider_result["suggestions"]:
            suggestion: EntitySuggestion = {
                **provider_suggestion,
                "id": f"{provider.provider_id}_{provider_suggestion['id']}",
                "source": provider.provider_id,
                "existing_entity_ids": _existing_entity_ids(
                    provider_suggestion, entity_ids_by_group_address
                ),
            }
            if _matches(suggestion, suggestion_filter):
                result["suggestions"].append(suggestion)
    return result
