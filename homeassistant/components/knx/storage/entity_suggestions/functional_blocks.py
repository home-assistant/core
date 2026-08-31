"""Entity suggestions from KNX Information Model semantics of project data.

Matches functional block (FB) and datapoint application (DPA) semantics
parsed from ETS project data by xknxproject against DPA annotations of
the entity store schemas defined in `entity_store_schema.py`.
"""

from collections import Counter
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING, Any, ClassVar, Literal, override

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
from homeassistant.helpers import entity_registry as er

from ...const import DOMAIN
from ..const import CONF_DPT, CONF_GA_PASSIVE, CONF_GA_WRITE
from ..dpa import FUNCTIONAL_BLOCK_PLATFORMS
from ..entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from ..knx_selector import GASelector, GroupSelect, GroupSelectSchema, KNXSection
from ..util import dpt_string_to_dict
from .base import SuggestionProvider
from .const import (
    EntitySuggestion,
    PlatformSuggestion,
    ProviderResult,
    SuggestedGroupAddress,
)

if TYPE_CHECKING:
    from ...knx_module import KNXModule

# first xknxproject version parsing KNX Information Model semantics
MIN_SEMANTICS_PARSER_VERSION = AwesomeVersion("3.9.0")

type GaSlot = Literal["write", "state"]
# config path of a group select and index of one of its options
type GroupSelectOptionRef = tuple[tuple[str, ...], int]


@dataclass(frozen=True)
class DpaSlotTarget:
    """A `write` or `state` key of a GASelector a DPA can be assigned to."""

    # config path to the group address selector, eg. ("color", "ga_color")
    path: tuple[str, ...]
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
    path: tuple[str, ...],
    group_select: GroupSelectOptionRef | None,
) -> Iterator[tuple[tuple[str, ...], GASelector, GroupSelectOptionRef | None]]:
    """Yield GASelectors of a schema with their config path and group select scope."""
    if isinstance(validator, probatio.All):
        # AllSerializeFirst: only the first validator holds the UI schema
        yield from _iter_ga_selectors(validator.validators[0], path, group_select)
        return
    if isinstance(validator, probatio.Schema) and isinstance(validator.schema, dict):
        for marker, value in validator.schema.items():
            key_path = (*path, str(marker))
            if isinstance(value, GASelector):
                yield (key_path, value, group_select)
            elif isinstance(value, GroupSelect):
                # group select options nest config under the group selects key
                # and are mutually exclusive alternatives
                assert isinstance(value.schema, GroupSelectSchema)
                for index, option in enumerate(value.schema.validators):
                    yield from _iter_ga_selectors(
                        option.schema, key_path, (key_path, index)
                    )
            elif isinstance(value, KNXSection):
                yield from _iter_ga_selectors(value.schema, key_path, group_select)


@cache
def _collect_dpa_index(platform: Platform) -> dict[str, DpaSlotTarget]:
    """Map DPA ids (eg. "417.52") to their target key in a platform schema.

    First occurrence of a DPA wins.
    """
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
                index.setdefault(
                    dpa,
                    DpaSlotTarget(
                        path=path,
                        slot=slot,
                        selector=selector,
                        group_select=group_select,
                    ),
                )
    return index


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
    assignments: dict[tuple[str, ...], _SlotAssignment],
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
    assignments: dict[tuple[str, ...], _SlotAssignment],
    unmatched_dpas: set[str],
) -> None:
    """Drop assignments of all but the first matched group select option.

    Group select options are mutually exclusive alternatives, but a device may
    provide com objects matching multiple options (eg. combined and individual
    colour addresses). Option order marks preference (eg. combined colour
    addresses before individual ones).
    """
    # group select path -> option index -> assignment paths
    group_selects: dict[tuple[str, ...], dict[int, list[tuple[str, ...]]]] = {}
    for path, assignment in assignments.items():
        if assignment.group_select is None:
            continue
        gs_path, option = assignment.group_select
        group_selects.setdefault(gs_path, {}).setdefault(option, []).append(path)
    for options in group_selects.values():
        if len(options) <= 1:
            continue
        winning_option = min(options)
        for option, paths in options.items():
            if option == winning_option:
                continue
            for path in paths:
                unmatched_dpas.update(assignments[path].dpas)
                del assignments[path]


def _set_nested_value(
    config: dict[str, Any], path: tuple[str, ...], value: Any
) -> None:
    """Set a value in a nested config dict, creating intermediate dicts."""
    for key in path[:-1]:
        config = config.setdefault(key, {})
    config[path[-1]] = value


def _build_platform_suggestion(
    project: KNXProject,
    channel: ProjectChannel,
    dpa_index: dict[str, DpaSlotTarget],
) -> PlatformSuggestion | None:
    """Build the suggested `knx` config for one channel and platform schema."""
    assignments: dict[tuple[str, ...], _SlotAssignment] = {}
    unmatched_dpas: set[str] = set()

    for com_object_id in channel["communication_object_ids"]:
        # com objects without group address links are not included in the project data
        if (com_object := project["communication_objects"].get(com_object_id)) is None:
            continue
        for dpa in com_object["dpas"] or ():
            target = dpa_index.get(dpa)
            if target is None or not _try_assign_dpa(
                project, dpa, com_object, target, assignments
            ):
                unmatched_dpas.add(dpa)

    _resolve_group_select_options(assignments, unmatched_dpas)

    # a config without any write address can never validate for actuator platforms
    if not any(CONF_GA_WRITE in a.ga_schema for a in assignments.values()):
        return None

    knx_config: dict[str, Any] = {}
    matched_group_addresses: set[str] = set()
    for path, assignment in assignments.items():
        _set_nested_value(knx_config, path, assignment.ga_schema)
        matched_group_addresses.update(assignment.group_addresses)
    return PlatformSuggestion(
        knx=knx_config,
        # names carry the semantics a channel name often lacks
        matched_group_addresses=[
            SuggestedGroupAddress(
                address=address, name=project["group_addresses"][address]["name"]
            )
            for address in sorted(matched_group_addresses)
        ],
        unmatched_dpas=sorted(unmatched_dpas),
    )


class FunctionalBlockSuggestionProvider(SuggestionProvider):
    """Suggest entities from functional block semantics of imported project data."""

    # marks suggestions of this provider for the frontend
    provider_id: ClassVar[str] = "fb"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: KNXModule
    ) -> ProviderResult:
        """Generate entity suggestions from project data."""
        project = await knx.project.get_knxproject()
        if project is None:
            return ProviderResult(suggestions=[], hints={"state": "no_project"})

        parser_version = project["info"]["xknxproject_version"]
        if AwesomeVersion(parser_version) < MIN_SEMANTICS_PARSER_VERSION:
            return ProviderResult(
                suggestions=[],
                hints={"state": "outdated_parser", "parser_version": parser_version},
            )
        functional_blocks_found = {
            fb
            for device in project["devices"].values()
            for channel in device["channels"].values()
            for fb in channel["functional_blocks"] or ()
        }
        if not functional_blocks_found:
            return ProviderResult(suggestions=[], hints={"state": "no_semantics"})

        return ProviderResult(
            suggestions=self._build_suggestions(hass, knx, project),
            hints={
                "state": "ok",
                "functional_blocks_found": sorted(functional_blocks_found),
            },
        )

    def _build_suggestions(
        self, hass: HomeAssistant, knx: KNXModule, project: KNXProject
    ) -> list[EntitySuggestion]:
        """Build suggestions for all channels with supported functional blocks."""
        candidates = [
            candidate
            for device_address, device in project["devices"].items()
            for channel_id, channel in device["channels"].items()
            if (
                candidate := self._build_channel_suggestion(
                    project, device_address, channel_id, channel
                )
            )
            is not None
        ]
        self._add_existing_entity_ids(hass, knx, candidates)
        self._disambiguate_names(project, candidates)
        return candidates

    def _build_channel_suggestion(
        self,
        project: KNXProject,
        device_address: str,
        channel_id: str,
        channel: ProjectChannel,
    ) -> EntitySuggestion | None:
        """Build the suggestion for one channel, if it has supported functional blocks."""
        functional_blocks = [
            fb
            for fb in channel["functional_blocks"] or ()
            if fb in FUNCTIONAL_BLOCK_PLATFORMS
        ]
        # platforms able to represent the channels functional blocks - ordered, deduplicated
        platform_options = dict.fromkeys(
            platform
            for fb in functional_blocks
            for platform in FUNCTIONAL_BLOCK_PLATFORMS[fb]
        )
        suggestions = {
            platform.value: suggestion
            for platform in platform_options
            if (
                suggestion := _build_platform_suggestion(
                    project, channel, _collect_dpa_index(platform)
                )
            )
            is not None
        }
        if not suggestions:
            return None
        device = project["devices"][device_address]
        return EntitySuggestion(
            # channel ids are only unique within a device
            id=f"{device_address}_{channel_id}",
            source=self.provider_id,
            suggested_name=channel["name"] or device["name"],
            group_id=device_address,
            group_name=device["name"],
            secondary_info=channel["name"],
            platform_options=list(suggestions),
            suggestions=suggestions,
            existing_entity_ids=[],
            metadata={"functional_blocks": functional_blocks},
        )

    def _add_existing_entity_ids(
        self, hass: HomeAssistant, knx: KNXModule, candidates: list[EntitySuggestion]
    ) -> None:
        """Add entities already using one of the suggested group addresses."""
        entity_registry = er.async_get(hass)
        ga_entities = {
            str(ga): identifiers
            for ga, identifiers in knx.group_address_entities.items()
        }
        for candidate in candidates:
            candidate["existing_entity_ids"] = sorted(
                {
                    entity_id
                    for suggestion in candidate["suggestions"].values()
                    for ga in suggestion["matched_group_addresses"]
                    for identifier in ga_entities.get(ga["address"], ())
                    if (
                        entity_id := entity_registry.async_get_entity_id(
                            identifier.platform, DOMAIN, identifier.unique_id
                        )
                    )
                    is not None
                }
            )

    def _disambiguate_names(
        self, project: KNXProject, candidates: list[EntitySuggestion]
    ) -> None:
        """Prefix names used multiple times with their device name."""
        name_counts = Counter(candidate["suggested_name"] for candidate in candidates)
        for candidate in candidates:
            if (
                name_counts[candidate["suggested_name"]] > 1
                and candidate["secondary_info"]
            ):
                device = project["devices"][candidate["group_id"]]
                candidate["suggested_name"] = (
                    f"{device['name']} {candidate['secondary_info']}"
                )
