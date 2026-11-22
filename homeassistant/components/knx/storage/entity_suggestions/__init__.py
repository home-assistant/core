"""Entity suggestions from KNX data sources."""

from collections import defaultdict
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN
from ..const import CONF_GA_STATE, CONF_GA_WRITE
from .base import SuggestionProvider
from .const import (
    DuplicateSuggestion,
    EntitySuggestion,
    EntitySuggestionsResult,
    PlatformSuggestion,
    ProviderSuggestion,
    SuggestionFilter,
)
from .existing_config import ExistingConfigSuggestionProvider
from .functional_blocks import FunctionalBlockSuggestionProvider
from .functions import FunctionSuggestionProvider
from .ga_config import iter_ga_configs

if TYPE_CHECKING:
    from ...knx_module import KNXModule

# Ordered by how much a provider is to be trusted, most reliable first: a
# configuration the user already made, then device semantics, then building
# functions. The order ranks suggestions of different providers for the same
# thing - see `_link_duplicates` - and is the order of the response.
SUGGESTION_PROVIDERS: list[SuggestionProvider] = [
    ExistingConfigSuggestionProvider(),
    FunctionalBlockSuggestionProvider(),
    FunctionSuggestionProvider(),
]


def _entity_ids_by_group_address(
    hass: HomeAssistant, knx: KNXModule
) -> dict[str, list[str]]:
    """Map group addresses to the ids of entities using them, disabled ones included."""
    entity_registry = er.async_get(hass)
    return {
        group_address: [
            entity_id
            for entity in entities
            if (
                entity_id := entity_registry.async_get_entity_id(
                    entity["platform"], DOMAIN, entity["unique_id"]
                )
            )
            is not None
        ]
        for group_address, entities in knx.get_group_address_entities().items()
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


def _identifying_addresses(platform_suggestion: PlatformSuggestion) -> set[str]:
    """Return the group addresses telling what a suggested entity controls.

    These are the addresses it writes to: two entities of a platform sending
    to the same address are the same thing, while a state address may be shared
    - eg. a common feedback. A suggestion that writes nothing, like a sensor,
    is identified by the addresses it reads. Passive addresses and addresses a
    provider doesn't report as matched - eg. ones shared with other channels -
    are not considered.
    """
    matched = {
        group_address["address"]
        for group_address in platform_suggestion["matched_group_addresses"]
    }
    ga_configs = [
        ga_config for _, ga_config in iter_ga_configs(platform_suggestion["knx"])
    ]
    for slot in (CONF_GA_WRITE, CONF_GA_STATE):
        if addresses := {
            address
            for ga_config in ga_configs
            if (address := ga_config.get(slot)) in matched
        }:
            return addresses
    return set()


def _link_duplicates(suggestions: list[EntitySuggestion]) -> None:
    """Link suggestions of different providers for the same thing.

    `suggestions` are ordered by the rank of their provider. Two suggestions
    are duplicates if they share an identifying group address on a platform
    both can be created as. Suggestions of the same provider are not linked: a
    provider may offer alternatives on purpose. Links are pairwise - if A and
    C both duplicate B, A and C are not necessarily duplicates of each other.
    """
    # (platform, group address) -> indexes of the suggestions identified by it
    by_address: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    for index, suggestion in enumerate(suggestions):
        for platform, platform_suggestion in suggestion["suggestions"].items():
            for address in _identifying_addresses(platform_suggestion):
                by_address[(platform, address)].append(index)

    # index of a suggestion -> index of a duplicate -> shared (platform, address)
    shared: defaultdict[int, defaultdict[int, list[tuple[str, str]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for key, indexes in by_address.items():
        for index in indexes:
            for other in indexes:
                if suggestions[index]["source"] != suggestions[other]["source"]:
                    shared[index][other].append(key)

    for index, duplicates in shared.items():
        suggestion = suggestions[index]
        # sorted by index is sorted by provider rank
        for other, keys in sorted(duplicates.items()):
            duplicate = suggestions[other]
            suggestion["duplicates"].append(
                DuplicateSuggestion(
                    id=duplicate["id"],
                    source=duplicate["source"],
                    suggested_name=duplicate["suggested_name"],
                    group_id=duplicate["group_id"],
                    group_name=duplicate["group_name"],
                    platforms=[
                        platform
                        for platform in suggestion["platform_options"]
                        if any(platform == key[0] for key in keys)
                    ],
                    group_addresses=sorted({address for _, address in keys}),
                )
            )
        if (best := min(duplicates)) < index:
            suggestion["superseded_by"] = suggestions[best]["id"]


def _drop_superseded(suggestions: list[EntitySuggestion]) -> list[EntitySuggestion]:
    """Drop suggestions a duplicate of a preferred provider in the list stands for.

    A suggestion is only dropped in favor of one that is returned - a filter
    never hides something without showing its replacement.
    """
    rank = {
        provider.provider_id: index
        for index, provider in enumerate(SUGGESTION_PROVIDERS)
    }
    returned = {suggestion["id"] for suggestion in suggestions}
    return [
        suggestion
        for suggestion in suggestions
        if not any(
            duplicate["id"] in returned
            and rank[duplicate["source"]] < rank[suggestion["source"]]
            for duplicate in suggestion["duplicates"]
        )
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

    Providers generate everything they know about. Duplicate detection - against
    existing entities and between providers - and filtering are done here so
    they behave the same for every source. Duplicates are linked before
    filtering, so a filtered response still reports them.
    Suggestions are returned in the order of `SUGGESTION_PROVIDERS`.
    Results are not windowed - a caller that has to bound its response
    applies its own limit.
    """
    suggestion_filter = suggestion_filter or SuggestionFilter()
    entity_ids_by_group_address = _entity_ids_by_group_address(hass, knx)
    result = EntitySuggestionsResult(suggestions=[], providers={})
    suggestions: list[EntitySuggestion] = []
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
                "duplicates": [],
                "superseded_by": None,
            }
            suggestions.append(suggestion)
    _link_duplicates(suggestions)
    suggestions = [
        suggestion
        for suggestion in suggestions
        if _matches(suggestion, suggestion_filter)
    ]
    if not suggestion_filter.include_superseded:
        suggestions = _drop_superseded(suggestions)
    result["suggestions"] = suggestions
    return result
