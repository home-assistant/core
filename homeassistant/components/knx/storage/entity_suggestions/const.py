"""Types for KNX entity suggestions."""

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass(frozen=True)
class SuggestionFilter:
    """Narrow down which entity suggestions are returned.

    Generating every suggestion of a large project is cheap, but sending them
    all is not - a caller that only wants the covers of one device shouldn't
    have to receive the whole installation. Field metadata descriptions follow
    the convention of the library `*.mcp` input dataclasses, so a parameter
    schema can be derived from this class.
    """

    platform: str | None = field(
        default=None,
        metadata={
            "description": (
                'Only suggestions that can be created as this platform, e.g. "light".'
            )
        },
    )
    group_id: str | None = field(
        default=None,
        metadata={
            "description": (
                "Only suggestions of this group - for suggestions from project data "
                'the individual address of the device, e.g. "1.1.5".'
            )
        },
    )
    include_configured: bool = field(
        default=True,
        metadata={
            "description": (
                "Include suggestions whose group addresses are already used by an "
                "existing entity."
            )
        },
    )


class SuggestedGroupAddress(TypedDict):
    """A group address used by a suggested entity configuration."""

    address: str
    name: str


class PlatformSuggestion(TypedDict):
    """Suggested entity configuration for one platform."""

    # `knx` options of EntityData
    knx: dict[str, Any]
    # group addresses used in `knx` - for duplicate detection and display
    matched_group_addresses: list[SuggestedGroupAddress]
    # informative: DPAs of the source that were not assigned to a config key
    unmatched_dpas: list[str]


class EntitySuggestion(TypedDict):
    """A suggested entity, possibly representable by multiple platforms."""

    # unique id - prefixed with the providers id by the orchestrator
    id: str
    # provider id this suggestion originates from
    source: str
    suggested_name: str
    # group suggestions belong to, eg. a device; `group_id` is stable, `group_name`
    # is for display - callers compose their own title from both
    group_id: str
    group_name: str
    # additional info for the suggestion, eg. a channel name
    secondary_info: str
    # platforms able to represent this suggestion - first item is the default
    platform_options: list[str]
    # key: platform
    suggestions: dict[str, PlatformSuggestion]
    # entities already using one of the matched group addresses
    existing_entity_ids: list[str]
    # provider specific details about where the suggestion comes from
    metadata: dict[str, Any]


class ProviderResult(TypedDict):
    """Result of a single suggestion provider."""

    suggestions: list[EntitySuggestion]
    # provider specific information, eg. for empty-state hints
    hints: dict[str, Any]


class EntitySuggestionsResult(TypedDict):
    """Combined result of all suggestion providers."""

    suggestions: list[EntitySuggestion]
    # key: provider id
    providers: dict[str, dict[str, Any]]
