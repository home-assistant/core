"""Entity suggestions from KNX Information Model semantics of project data.

Matches functional block (FB) and datapoint application (DPA) semantics
parsed from ETS project data by xknxproject against DPA annotations of
the entity store schemas defined in `entity_store_schema.py`.
"""

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from functools import cache
from typing import TYPE_CHECKING, Any, Final, Literal, Required, TypedDict, override

from awesomeversion import AwesomeVersion
import probatio
from xknx.typing import DPTMainSubDict
from xknxproject.models import (
    Channel as ProjectChannel,
    CommunicationObject,
    DPTType,
    KNXProject,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from ..const import CONF_DPT, CONF_GA_PASSIVE
from ..entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from ..knx_selector import (
    GASelector,
    GroupSelect,
    GroupSelectSchema,
    KNXSection,
    knx_selector_in,
)
from ..util import dpt_string_to_dict
from .base import SuggestionProvider
from .const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)

if TYPE_CHECKING:
    from ...knx_module import KNXModule

# first xknxproject version parsing KNX Information Model semantics
MIN_SEMANTICS_PARSER_VERSION = AwesomeVersion("3.9.0")

# default platform of functional blocks representable by multiple platforms
FUNCTIONAL_BLOCK_DEFAULT_PLATFORM: Final = {"417": Platform.LIGHT}

type ConfigPath = tuple[str, ...]
type GaSlot = Literal["write", "state"]


class SemanticsState(StrEnum):
    """Availability of KNX Information Model semantics in the project data."""

    NO_PROJECT = "no_project"
    OUTDATED_PARSER = "outdated_parser"
    NO_SEMANTICS = "no_semantics"
    OK = "ok"


class FunctionalBlockHints(TypedDict, total=False):
    """Hints of the functional block provider."""

    state: Required[SemanticsState]
    parser_version: str
    functional_blocks_found: list[str]


@dataclass(frozen=True)
class GroupSelectOptionRef:
    """One option of a group select - options are mutually exclusive alternatives."""

    # config path of the group select, eg. ("color",)
    path: ConfigPath
    # position in the group select - lower is preferred
    index: int


@dataclass(frozen=True)
class DpaSlotTarget:
    """A `write` or `state` key of a GASelector a DPA can be assigned to."""

    # config path to the group address selector, eg. ("color", "ga_color")
    path: ConfigPath
    slot: GaSlot
    selector: GASelector
    # set when the selector is inside a group select option
    group_select: GroupSelectOptionRef | None = None


@dataclass
class _SlotAssignment:
    """Group address config assigned to one config key."""

    ga_schema: dict[str, Any]
    group_select: GroupSelectOptionRef | None
    # DPAs assigned to this config key
    dpas: list[str] = field(default_factory=list)
    # group addresses used by this config key (including passive)
    group_addresses: set[str] = field(default_factory=set)


def _iter_ga_selectors(
    validator: Any,
    path: ConfigPath,
    group_select: GroupSelectOptionRef | None,
) -> Iterator[tuple[ConfigPath, GASelector, GroupSelectOptionRef | None]]:
    """Yield GASelectors of a schema with their config path and group select scope."""
    if isinstance(validator, probatio.All):
        # AllSerializeFirst: only the first validator holds the UI schema
        yield from _iter_ga_selectors(validator.validators[0], path, group_select)
        return
    if isinstance(validator, probatio.Schema):
        if not isinstance(validator.schema, dict):
            # DataclassSchema: the fields are compiled into a nested schema
            yield from _iter_ga_selectors(validator.schema, path, group_select)
            return
        for marker, value in validator.schema.items():
            key_path = (*path, str(marker))
            if isinstance(value, probatio.All):
                # dataclass field: the selector is in the `Annotated` metadata
                value = knx_selector_in(value.validators)
            if isinstance(value, GASelector):
                yield (key_path, value, group_select)
            elif isinstance(value, GroupSelect):
                assert isinstance(value.schema, GroupSelectSchema)
                for index, option in enumerate(value.schema.validators):
                    yield from _iter_ga_selectors(
                        option.schema, key_path, GroupSelectOptionRef(key_path, index)
                    )
            elif isinstance(value, KNXSection):
                yield from _iter_ga_selectors(value.schema, key_path, group_select)


@cache
def _collect_dpa_index(platform: Platform) -> dict[str, DpaSlotTarget]:
    """Map DPA ids (eg. "417.52") to their target key in a platform schema."""
    index: dict[str, DpaSlotTarget] = {}
    for path, selector, group_select in _iter_ga_selectors(
        KNX_SCHEMA_FOR_PLATFORM[platform], (), None
    ):
        slot_dpas: dict[GaSlot, Iterable[str] | None] = {
            "write": selector.dpa_write,
            "state": selector.dpa_state,
        }
        for slot, dpas in slot_dpas.items():
            for dpa in dpas or ():
                if dpa in index:
                    raise ValueError(
                        f"DPA {dpa} is annotated multiple times in the {platform} schema"
                    )
                index[str(dpa)] = DpaSlotTarget(
                    path=path,
                    slot=slot,
                    selector=selector,
                    group_select=group_select,
                )
    return index


@cache
def _functional_block_platforms() -> dict[str, list[Platform]]:
    """Map functional block numbers to platforms whose schema annotates DPAs of them.

    The first platform of a functional block is the default suggestion.
    """
    platforms_by_block: dict[str, set[Platform]] = {}
    for platform in KNX_SCHEMA_FOR_PLATFORM:
        for dpa in _collect_dpa_index(platform):
            block = dpa.partition(".")[0]
            platforms_by_block.setdefault(block, set()).add(platform)

    result: dict[str, list[Platform]] = {}
    for block, platforms in platforms_by_block.items():
        ordered = sorted(platforms)
        if (default := FUNCTIONAL_BLOCK_DEFAULT_PLATFORM.get(block)) in ordered:
            ordered.remove(default)
            ordered.insert(0, default)
        result[block] = ordered
    return result


def _selector_dpt_enum(selector: GASelector) -> type[Enum] | None:
    """Return the selectors dpt enum, if it uses one."""
    if isinstance(selector.dpt, type) and issubclass(selector.dpt, Enum):
        return selector.dpt
    return None


def _dpt_matches(ga_dpt: DPTType | None, valid_dpt: DPTMainSubDict) -> bool:
    """Check whether a group address DPT matches a valid DPT (sub None matches any)."""
    return (
        ga_dpt is not None
        and ga_dpt["main"] == valid_dpt["main"]
        and (valid_dpt["sub"] is None or ga_dpt["sub"] == valid_dpt["sub"])
    )


def _ga_dpt_valid_for_selector(ga_dpt: DPTType | None, selector: GASelector) -> bool:
    """Check whether a group addresses DPT is accepted by a GASelector."""
    if selector.valid_dpt is not None:
        return any(
            _dpt_matches(ga_dpt, dpt_string_to_dict(dpt)) for dpt in selector.valid_dpt
        )
    if (dpt_enum := _selector_dpt_enum(selector)) is not None:
        return any(
            _dpt_matches(ga_dpt, dpt_string_to_dict(item.value)) for item in dpt_enum
        )
    # dpt-class lists or no restriction: don't reject based on project DPT
    return True


def _dpt_select_value(ga_dpt: DPTType | None, selector: GASelector) -> str | None:
    """Value for the `dpt` config key of dpt-enum selectors matching a group addresses DPT."""
    if (dpt_enum := _selector_dpt_enum(selector)) is None:
        return None
    return next(
        (
            str(item.value)
            for item in dpt_enum
            if _dpt_matches(ga_dpt, dpt_string_to_dict(item.value))
        ),
        None,
    )


def _try_assign_dpa(
    project: KNXProject,
    dpa: str,
    com_object: CommunicationObject,
    target: DpaSlotTarget,
    assignments: dict[ConfigPath, _SlotAssignment],
) -> bool:
    """Assign a com objects group addresses to the config key targeted by a DPA.

    The first linked group address fills the targeted `write` or `state` key,
    additional links become `passive` addresses.
    Returns False if the DPA can not be assigned.
    """
    ga_links = [
        ga
        for ga in com_object["group_address_links"]
        if ga in project["group_addresses"]
    ]
    if not ga_links:
        return False
    primary_ga = ga_links[0]
    ga_dpt = project["group_addresses"][primary_ga]["dpt"]
    if not _ga_dpt_valid_for_selector(ga_dpt, target.selector):
        return False
    assignment = assignments.get(target.path)
    if assignment is not None and target.slot in assignment.ga_schema:
        # slot already assigned by another com object - first wins
        return False
    if assignment is None:
        assignment = _SlotAssignment(ga_schema={}, group_select=target.group_select)
        assignments[target.path] = assignment

    assignment.ga_schema[target.slot] = primary_ga
    if (dpt_value := _dpt_select_value(ga_dpt, target.selector)) is not None:
        assignment.ga_schema[CONF_DPT] = dpt_value
    assignment.dpas.append(dpa)
    assignment.group_addresses.add(primary_ga)
    if target.selector.passive and len(ga_links) > 1:
        passive: list[str] = assignment.ga_schema.setdefault(CONF_GA_PASSIVE, [])
        passive.extend(ga for ga in ga_links[1:] if ga not in passive)
        assignment.group_addresses.update(ga_links[1:])
    return True


def _resolve_group_select_options(
    assignments: dict[ConfigPath, _SlotAssignment],
    unmatched: set[str],
) -> None:
    """Drop assignments of all but the preferred matched group select option.

    A device may provide com objects matching multiple options (eg. combined
    and individual colour addresses).
    """
    # group select path -> option index -> assignment paths
    group_selects: dict[ConfigPath, dict[int, list[ConfigPath]]] = {}
    for path, assignment in assignments.items():
        if assignment.group_select is None:
            continue
        option = assignment.group_select
        group_selects.setdefault(option.path, {}).setdefault(option.index, []).append(
            path
        )
    for options in group_selects.values():
        if len(options) <= 1:
            continue
        winning_option = min(options)
        for option_index, paths in options.items():
            if option_index == winning_option:
                continue
            for path in paths:
                unmatched.update(assignments[path].dpas)
                del assignments[path]


def _set_nested_value(config: dict[str, Any], path: ConfigPath, value: Any) -> None:
    """Set a value in a nested config dict, creating intermediate dicts."""
    for key in path[:-1]:
        config = config.setdefault(key, {})
    config[path[-1]] = value


def _validates(platform: Platform, knx_config: dict[str, Any]) -> bool:
    """Check whether a suggested `knx` config passes the platform schema."""
    try:
        KNX_SCHEMA_FOR_PLATFORM[platform](knx_config)
    except probatio.Invalid:
        return False
    return True


def _build_platform_suggestion(
    project: KNXProject,
    channel: ProjectChannel,
    platform: Platform,
) -> PlatformSuggestion | None:
    """Build the suggested `knx` config for one channel and platform schema."""
    dpa_index = _collect_dpa_index(platform)
    assignments: dict[ConfigPath, _SlotAssignment] = {}
    unmatched: set[str] = set()

    for com_object_id in channel["communication_object_ids"]:
        # com objects without group address links are not included in the project data
        if (com_object := project["communication_objects"].get(com_object_id)) is None:
            continue
        for dpa in com_object["dpas"] or ():
            target = dpa_index.get(dpa)
            if target is None or not _try_assign_dpa(
                project, dpa, com_object, target, assignments
            ):
                unmatched.add(dpa)

    _resolve_group_select_options(assignments, unmatched)

    knx_config: dict[str, Any] = {}
    matched_group_addresses: set[str] = set()
    for path, assignment in assignments.items():
        _set_nested_value(knx_config, path, assignment.ga_schema)
        matched_group_addresses.update(assignment.group_addresses)

    # the schema decides what a complete configuration needs - eg. a write address
    if not assignments or not _validates(platform, knx_config):
        return None

    return PlatformSuggestion(
        knx=knx_config,
        # names carry the semantics a channel name often lacks
        matched_group_addresses=[
            SuggestedGroupAddress(
                address=address, name=project["group_addresses"][address]["name"]
            )
            for address in sorted(matched_group_addresses)
        ],
        unmatched=sorted(unmatched),
    )


def _build_channel_suggestion(
    project: KNXProject,
    device_address: str,
    channel_id: str,
    channel: ProjectChannel,
) -> ProviderSuggestion | None:
    """Build the suggestion for one channel, if it has supported functional blocks."""
    functional_block_platforms = _functional_block_platforms()
    functional_blocks = [
        fb
        for fb in channel["functional_blocks"] or ()
        if fb in functional_block_platforms
    ]
    # platforms able to represent the channels functional blocks - ordered, deduplicated
    platform_options = dict.fromkeys(
        platform
        for fb in functional_blocks
        for platform in functional_block_platforms[fb]
    )
    suggestions = {
        platform.value: suggestion
        for platform in platform_options
        if (suggestion := _build_platform_suggestion(project, channel, platform))
        is not None
    }
    if not suggestions:
        return None
    device = project["devices"][device_address]
    return ProviderSuggestion(
        # channel ids are only unique within a device
        id=f"{device_address}_{channel_id}",
        suggested_name=channel["name"] or device["name"],
        group_id=device_address,
        group_name=device["name"],
        secondary_info=channel["name"],
        platform_options=list(suggestions),
        suggestions=suggestions,
        metadata={"functional_blocks": functional_blocks},
    )


def _disambiguate_names(candidates: list[ProviderSuggestion]) -> None:
    """Prefix names used multiple times with their device name."""
    name_counts = Counter(candidate["suggested_name"] for candidate in candidates)
    for candidate in candidates:
        if name_counts[candidate["suggested_name"]] > 1 and candidate["secondary_info"]:
            candidate["suggested_name"] = (
                f"{candidate['group_name']} {candidate['secondary_info']}"
            )


def _build_suggestions(project: KNXProject) -> list[ProviderSuggestion]:
    """Build suggestions for all channels with supported functional blocks."""
    candidates = [
        candidate
        for device_address, device in project["devices"].items()
        for channel_id, channel in device["channels"].items()
        if (
            candidate := _build_channel_suggestion(
                project, device_address, channel_id, channel
            )
        )
        is not None
    ]
    _disambiguate_names(candidates)
    return candidates


class FunctionalBlockSuggestionProvider(SuggestionProvider):
    """Suggest entities from functional block semantics of imported project data."""

    provider_id = "fb"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: KNXModule
    ) -> ProviderResult:
        """Generate entity suggestions from project data."""
        project = await knx.project.get_knxproject()
        if project is None:
            return ProviderResult(
                suggestions=[],
                hints=FunctionalBlockHints(state=SemanticsState.NO_PROJECT),
            )

        parser_version = project["info"]["xknxproject_version"]
        if AwesomeVersion(parser_version) < MIN_SEMANTICS_PARSER_VERSION:
            return ProviderResult(
                suggestions=[],
                hints=FunctionalBlockHints(
                    state=SemanticsState.OUTDATED_PARSER,
                    parser_version=parser_version,
                ),
            )
        functional_blocks_found = {
            fb
            for device in project["devices"].values()
            for channel in device["channels"].values()
            for fb in channel["functional_blocks"] or ()
        }
        if not functional_blocks_found:
            return ProviderResult(
                suggestions=[],
                hints=FunctionalBlockHints(state=SemanticsState.NO_SEMANTICS),
            )

        return ProviderResult(
            suggestions=_build_suggestions(project),
            hints=FunctionalBlockHints(
                state=SemanticsState.OK,
                functional_blocks_found=sorted(functional_blocks_found),
            ),
        )
