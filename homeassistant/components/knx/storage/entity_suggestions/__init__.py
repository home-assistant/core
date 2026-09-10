"""Entity suggestions from KNX data sources."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant

from .base import SuggestionProvider
from .const import EntitySuggestion, EntitySuggestionsResult, SuggestionFilter
from .functional_blocks import FunctionalBlockSuggestionProvider

if TYPE_CHECKING:
    from ...knx_module import KNXModule

SUGGESTION_PROVIDERS: list[type[SuggestionProvider]] = [
    FunctionalBlockSuggestionProvider,
]


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

    Providers generate everything they know about; filtering is applied here so
    it behaves the same for every source. Results are not windowed - a caller
    that has to bound its response applies its own limit.
    """
    suggestion_filter = suggestion_filter or SuggestionFilter()
    result = EntitySuggestionsResult(suggestions=[], providers={})
    for provider_class in SUGGESTION_PROVIDERS:
        provider = provider_class()
        provider_result = await provider.async_get_suggestions(hass, knx)
        for suggestion in provider_result["suggestions"]:
            suggestion["id"] = f"{provider.provider_id}_{suggestion['id']}"
            if _matches(suggestion, suggestion_filter):
                result["suggestions"].append(suggestion)
        result["providers"][provider.provider_id] = provider_result["hints"]
    return result
