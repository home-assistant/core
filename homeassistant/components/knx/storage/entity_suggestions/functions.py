"""Entity suggestions from the building functions of project data.

A function of a room or other space (switchable light, dimmable light, sun
protection, heating, socket, ...) has a type from the KNX master data and links
group addresses in roles - the function points of its type. Most projects have
functions, while KNX Information Model semantics of channels are still rare.

Each role maps to a datapoint of the KNX Information Model, which resolves to
its config key through the DPA annotations of the platform schema (climate has
none yet and maps its roles to config keys itself).

- A stored role of the function type is used when the selector of its config key
  accepts the DPT of the group address.
- A group address without a stored role only gets one when its DPT fits exactly
  one free function point of the type, and no other such address fits that point.
  Otherwise, and without a DPT, it is left unmatched: a wrong guess writes to the
  wrong address, which is worse than no suggestion.
- A command role (written by the entity) only goes to a group address a linked
  communication object receives (communication and write flags), as far as the
  project knows its links.
"""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from functools import cache
from typing import TYPE_CHECKING, Any, Final, Required, TypedDict, override

from awesomeversion import AwesomeVersion
import probatio
from xknxproject.models import DPTType, Function, KNXProject, Space

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .. import dpa
from ..const import CONF_DPT, CONF_GA_PASSIVE
from ..entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from ..knx_selector import GASelector
from .base import SuggestionProvider
from .const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)
from .functional_blocks import (
    ConfigPath,
    GaSlot,
    _collect_dpa_index,
    _dpt_select_value,
    _ga_dpt_valid_for_selector,
    _iter_ga_selectors,
)

if TYPE_CHECKING:
    from ...knx_module import KNXModule

# first xknxproject version parsing the functions of a project
MIN_FUNCTIONS_PARSER_VERSION = AwesomeVersion("3.3.0")

# Function type -> (role, DPT) of each function point in the master data order
FUNCTION_POINTS: Final[dict[str, tuple[tuple[str, tuple[int, int]], ...]]] = {
    # switchable light
    "FT-1": (("SwitchOnOff", (1, 1)), ("InfoOnOff", (1, 1))),
    # dimmable light (deprecated)
    "FT-2": (
        ("SwitchOnOff", (1, 1)),
        ("DimmingControl", (3, 7)),
        ("InfoDimmingValue", (5, 1)),
        ("InfoOnOff", (1, 1)),
    ),
    # sun protection (deprecated)
    "FT-3": (
        ("MoveUpDown", (1, 8)),
        ("StopStepUpDown", (1, 7)),
        ("WindAlarm", (1, 5)),
        ("RainAlarm", (1, 5)),
    ),
    # heating radiator, heating floor (deprecated)
    "FT-4": (
        ("TempRoom", (9, 1)),
        ("TempRoomSetpoint", (9, 1)),
        ("ValvePosition", (5, 1)),
        ("HVACMode", (20, 102)),
        ("WindowStatus", (1, 19)),
    ),
    "FT-5": (
        ("TempRoom", (9, 1)),
        ("TempRoomSetpoint", (9, 1)),
        ("ValvePosition", (5, 1)),
        ("HVACMode", (20, 102)),
        ("WindowStatus", (1, 19)),
    ),
    # dimmable light
    "FT-6": (
        ("SwitchOnOff", (1, 1)),
        ("DimmingControl", (3, 7)),
        ("DimmingValue", (5, 1)),
        ("InfoOnOff", (1, 1)),
        ("InfoDimmingValue", (5, 1)),
    ),
    # sun protection
    "FT-7": (
        ("MoveUpDown", (1, 8)),
        ("StopStepUpDown", (1, 7)),
        ("WindAlarm", (1, 5)),
        ("RainAlarm", (1, 5)),
        ("CurrentAbsolutePositionBlindsPercentage", (5, 1)),
        ("CurrentAbsolutePositionSlatPercentage", (5, 1)),
    ),
    # heating (switching variable)
    "FT-8": (
        ("TempRoom", (9, 1)),
        ("TempRoomSetpoint", (9, 1)),
        ("ValveSwitch", (1, 1)),
        ("HVACMode", (20, 102)),
        ("WindowStatus", (1, 19)),
    ),
    # heating (continuous variable)
    "FT-9": (
        ("TempRoom", (9, 1)),
        ("TempRoomSetpoint", (9, 1)),
        ("ValvePosition", (5, 1)),
        ("HVACMode", (20, 102)),
        ("WindowStatus", (1, 19)),
    ),
    # socket
    "FT-10": (("SwitchOnOff", (1, 1)), ("InfoOnOff", (1, 1))),
}

# role -> config path and slots of its group address, for a schema without DPAs
type RoleConfig = dict[str, tuple[ConfigPath, tuple[GaSlot, ...]]]


@dataclass(frozen=True)
class FunctionEntity:
    """The entity of a function type and the datapoint of each of its roles.

    Roles not listed are not used. All `required` roles have to be linked.
    """

    platform: Platform
    # role -> datapoint (DPA) annotated in the platform schema
    dpas: Mapping[str, str]
    required: tuple[str, ...]
    # roles of a platform schema without DPA annotations
    roles: RoleConfig = field(default_factory=dict)


@dataclass(frozen=True)
class RoleTarget:
    """A `write` or `state` key of the config a role's group address goes to."""

    path: ConfigPath
    slot: GaSlot
    selector: GASelector


_SWITCH_DPAS: Final = {
    "SwitchOnOff": dpa.FB417.SWITCH_ON_OFF,
    "InfoOnOff": dpa.FB417.INFO_ON_OFF,
}
_DIMMING_DPAS: Final = {
    "SwitchOnOff": dpa.FB418.SWITCH_ON_OFF,
    "InfoOnOff": dpa.FB418.INFO_ON_OFF,
}
_SUN_PROTECTION_DPAS: Final = {
    "MoveUpDown": dpa.FB800.MOVE_UP_DOWN,
    "StopStepUpDown": dpa.FB800.STOP_STEP_UP_DOWN,
}
_COVER_DPAS: Final = {
    **_SUN_PROTECTION_DPAS,
    "CurrentAbsolutePositionBlindsPercentage": (
        dpa.FB800.CURRENT_ABS_POS_BLINDS_PERCENT
    ),
    "CurrentAbsolutePositionSlatPercentage": dpa.FB800.CURRENT_ABS_POS_SLATS_PERCENT,
}
# the setpoint is an absolute temperature - written and read back on one address
_CLIMATE_ROLES: Final[RoleConfig] = {
    "TempRoom": (("ga_temperature_current",), ("state",)),
    "TempRoomSetpoint": (
        ("target_temperature", "ga_temperature_target"),
        ("write", "state"),
    ),
    "HVACMode": (("ga_operation_mode",), ("write", "state")),
    "ValvePosition": (("ga_valve",), ("state",)),
    # a switching valve tells whether the room is being heated
    "ValveSwitch": (("ga_active",), ("state",)),
}
_CLIMATE: Final = FunctionEntity(
    Platform.CLIMATE, {}, ("TempRoomSetpoint", "TempRoom"), _CLIMATE_ROLES
)

FUNCTION_ENTITIES: Final[dict[str, FunctionEntity]] = {
    "FT-1": FunctionEntity(Platform.LIGHT, _SWITCH_DPAS, ("SwitchOnOff",)),
    "FT-2": FunctionEntity(
        Platform.LIGHT,
        # "value" is the brightness command of this type (Characteristics
        # "central" in the master data); relative dimming is no brightness
        {**_DIMMING_DPAS, "InfoDimmingValue": dpa.FB418.ABS_SETVALUE_CONTROL},
        ("SwitchOnOff",),
    ),
    "FT-3": FunctionEntity(Platform.COVER, _SUN_PROTECTION_DPAS, ("MoveUpDown",)),
    "FT-4": _CLIMATE,
    "FT-5": _CLIMATE,
    "FT-6": FunctionEntity(
        Platform.LIGHT,
        {
            **_DIMMING_DPAS,
            "DimmingValue": dpa.FB418.ABS_SETVALUE_CONTROL,
            "InfoDimmingValue": dpa.FB418.ACTUAL_DIMMING_VALUE,
        },
        ("SwitchOnOff",),
    ),
    "FT-7": FunctionEntity(Platform.COVER, _COVER_DPAS, ("MoveUpDown",)),
    "FT-8": _CLIMATE,
    "FT-9": _CLIMATE,
    "FT-10": FunctionEntity(Platform.SWITCH, _SWITCH_DPAS, ("SwitchOnOff",)),
}


@cache
def _selectors(platform: Platform) -> dict[ConfigPath, GASelector]:
    """Map the config paths of a platform schema to their GASelector.

    A path in several options of a group select is the one of the first option.
    """
    found: dict[ConfigPath, GASelector] = {}
    for path, selector, _group_select in _iter_ga_selectors(
        KNX_SCHEMA_FOR_PLATFORM[platform], (), None
    ):
        found.setdefault(path, selector)
    return found


@cache
def _role_targets(function_type: str) -> dict[str, tuple[RoleTarget, ...]]:
    """Map the roles of a function type to the config keys of its entity.

    An entity shared by several function types only takes the roles of the type.
    """
    if (entity := FUNCTION_ENTITIES.get(function_type)) is None:
        return {}
    points = {role for role, _dpt in FUNCTION_POINTS[function_type]}
    targets: dict[str, tuple[RoleTarget, ...]] = {}
    dpa_index = _collect_dpa_index(entity.platform)
    for role, role_dpa in entity.dpas.items():
        if role in points:
            target = dpa_index[role_dpa]
            targets[role] = (RoleTarget(target.path, target.slot, target.selector),)
    selectors = _selectors(entity.platform)
    for role, (path, slots) in entity.roles.items():
        if role in points:
            targets[role] = tuple(
                RoleTarget(path, slot, selectors[path]) for slot in slots
            )
    return targets


class FunctionsState(StrEnum):
    """Availability of building functions in the project data."""

    NO_PROJECT = "no_project"
    OUTDATED_PARSER = "outdated_parser"
    NO_FUNCTIONS = "no_functions"
    OK = "ok"


class FunctionHints(TypedDict, total=False):
    """Hints of the functions provider."""

    state: Required[FunctionsState]
    parser_version: str
    function_types_found: list[str]


@dataclass(frozen=True)
class LinkedObjects:
    """What the communication objects linked to each group address do.

    Only objects with the communication flag take part on the bus. Group
    addresses without a linked object in the project are not included: whether
    anything receives or answers them is unknown.
    """

    # a linked object receives the group address (write flag)
    receives: dict[str, bool]
    # a linked object answers reads of the group address (read flag)
    answers: dict[str, bool]


def _linked_objects(project: KNXProject) -> LinkedObjects:
    """Collect what the communication objects linked to each group address do."""
    receives: dict[str, bool] = {}
    answers: dict[str, bool] = {}
    for com_object in (project.get("communication_objects") or {}).values():
        flags = com_object["flags"]
        for address in com_object["group_address_links"]:
            receives[address] = receives.get(address, False) or (
                flags["communication"] and flags["write"]
            )
            answers[address] = answers.get(address, False) or (
                flags["communication"] and flags["read"]
            )
    return LinkedObjects(receives, answers)


def _fits(dpt: DPTType, point: tuple[int, int]) -> bool:
    """Whether a group address of `dpt` fits a function point of DPT `point`.

    One with only a main number fits the points of that number. A subtype has to
    be the point's: another one of the same main number can be encoded
    differently (5.010 is a count, 5.001 a percentage).
    """
    main, sub = point
    return dpt["main"] == main and dpt["sub"] in (None, sub)


@dataclass
class FunctionRoles:
    """The group address of each role of a function, and the inferred roles."""

    addresses: dict[str, str] = field(default_factory=dict)
    inferred: set[str] = field(default_factory=set)


def _function_roles(
    project: KNXProject,
    function: Function,
    linked: LinkedObjects | None = None,
) -> FunctionRoles:
    """Map the roles of a function to the address of their group address.

    A stored role is kept when the selector of its config key accepts the group
    address; a further group address stored with the same role is left
    unmatched, so a second status address never becomes a command. A group
    address without a stored role gets one only when its DPT fits a single free
    function point that no other such address fits.
    """
    if linked is None:
        linked = _linked_objects(project)
    function_type = function["function_type"]
    point_dpts = dict(FUNCTION_POINTS.get(function_type, ()))
    targets = _role_targets(function_type)
    roles = FunctionRoles()

    def dpt_of(address: str) -> DPTType | None:
        group_address = project["group_addresses"].get(address)
        return group_address["dpt"] if group_address is not None else None

    def takes(address: str, role: str) -> bool:
        if role not in targets:
            return False
        dpt = dpt_of(address)
        # a stored role on an address without DPT is the user's statement
        if dpt is not None and not all(
            _ga_dpt_valid_for_selector(dpt, target.selector) for target in targets[role]
        ):
            return False
        # known receivers that all don't write: a command would reach no one
        is_command = any(target.slot == "write" for target in targets[role])
        return not is_command or linked.receives.get(address, True)

    without_role: list[str] = []
    for ref in function["group_addresses"].values():
        role, address = ref["role"], ref["address"]
        if role not in point_dpts:
            without_role.append(address)
        elif role not in roles.addresses and takes(address, role):
            roles.addresses[role] = address

    free = [role for role in point_dpts if role not in roles.addresses]
    fitting: dict[str, list[str]] = {}
    for address in without_role:
        if address in fitting or address in roles.addresses.values():
            continue
        if (dpt := dpt_of(address)) is None:
            continue
        fitting[address] = [role for role in free if _fits(dpt, point_dpts[role])]
    # a point that several addresses fit would be a guess as well, also when
    # another of them fits further points
    fitted_by = Counter(role for points in fitting.values() for role in points)
    for address, points in fitting.items():
        if len(points) != 1:
            continue
        role = points[0]
        if fitted_by[role] == 1 and takes(address, role):
            roles.addresses[role] = address
            roles.inferred.add(role)
    return roles


def _set_ga(
    config: dict[str, Any],
    target: RoleTarget,
    address: str,
    dpt: DPTType | None,
) -> None:
    """Set a group address in a nested `knx` config."""
    for key in target.path:
        config = config.setdefault(key, {})
    config.setdefault(CONF_GA_PASSIVE, [])
    config[target.slot] = address
    if (dpt_value := _dpt_select_value(dpt, target.selector)) is not None:
        config.setdefault(CONF_DPT, dpt_value)


def _build_platform_suggestion(
    project: KNXProject,
    function: Function,
    linked: LinkedObjects | None = None,
) -> tuple[Platform, PlatformSuggestion, dict[str, str]] | None:
    """Build the `knx` config of the entity a function becomes.

    Also returns whether each role used was stored or inferred.
    """
    if (entity := FUNCTION_ENTITIES.get(function["function_type"])) is None:
        return None
    if linked is None:
        linked = _linked_objects(project)
    roles = _function_roles(project, function, linked)
    if any(role not in roles.addresses for role in entity.required):
        return None
    targets = _role_targets(function["function_type"])
    # the role writing each config path; its feedback alone is no usable address
    writers = {
        target.path: role
        for role, role_targets in targets.items()
        for target in role_targets
        if target.slot == "write"
    }
    knx_config: dict[str, Any] = {}
    used: set[str] = set()
    used_roles: dict[str, str] = {}
    for role, role_targets in targets.items():
        if (address := roles.addresses.get(role)) is None:
            continue
        group_address = project["group_addresses"].get(address)
        dpt = group_address["dpt"] if group_address is not None else None
        for target in role_targets:
            if (writer := writers.get(target.path, role)) != role and (
                writer not in roles.addresses
            ):
                # eg. the brightness of a dimmable light without an absolute
                # brightness value: left unmatched, the light switches
                continue
            if (
                target.slot == "state"
                and writers.get(target.path) == role
                and not linked.answers.get(address, True)
            ):
                # reading the command address back: nothing would answer
                continue
            _set_ga(knx_config, target, address, dpt)
            used.add(address)
            used_roles[role] = "inferred" if role in roles.inferred else "stored"
    # the schema decides what a complete configuration needs
    try:
        KNX_SCHEMA_FOR_PLATFORM[entity.platform](knx_config)
    except probatio.Invalid:
        return None
    return (
        entity.platform,
        PlatformSuggestion(
            knx=knx_config,
            matched_group_addresses=[
                SuggestedGroupAddress(
                    address=address,
                    name=project["group_addresses"][address]["name"]
                    if address in project["group_addresses"]
                    else "",
                )
                for address in sorted(used)
            ],
            unmatched=sorted(
                {
                    ref["address"]
                    for ref in function["group_addresses"].values()
                    if ref["address"] not in used
                }
            ),
        ),
        used_roles,
    )


def _spaces(locations: dict[str, Space]) -> dict[str, Space]:
    """All spaces of the buildings by their identifier."""
    found: dict[str, Space] = {}
    for space in locations.values():
        found[space["identifier"]] = space
        found |= _spaces(space["spaces"])
    return found


def _build_suggestions(project: KNXProject) -> list[ProviderSuggestion]:
    """Build suggestions for all functions of a type with an entity."""
    spaces = _spaces(project.get("locations") or {})
    linked = _linked_objects(project)
    suggestions: list[ProviderSuggestion] = []
    for function_id, function in (project.get("functions") or {}).items():
        if (built := _build_platform_suggestion(project, function, linked)) is None:
            continue
        platform, platform_suggestion, used_roles = built
        space = spaces.get(function["space_id"])
        suggestions.append(
            ProviderSuggestion(
                id=function_id,
                suggested_name=function["name"],
                group_id=function["space_id"],
                group_name=space["name"] if space is not None else "",
                secondary_info=function["usage_text"],
                platform_options=[platform.value],
                suggestions={platform.value: platform_suggestion},
                metadata={
                    "function_type": function["function_type"],
                    # role -> "stored" in the project or "inferred" from the DPT
                    "roles": used_roles,
                },
            )
        )
    return suggestions


class FunctionSuggestionProvider(SuggestionProvider):
    """Suggest entities from the building functions of imported project data."""

    provider_id = "function"

    @override
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: KNXModule
    ) -> ProviderResult:
        """Generate entity suggestions from project data."""
        project = await knx.project.get_knxproject()
        if project is None:
            return ProviderResult(
                suggestions=[],
                hints=FunctionHints(state=FunctionsState.NO_PROJECT),
            )
        parser_version = project["info"]["xknxproject_version"]
        if AwesomeVersion(parser_version) < MIN_FUNCTIONS_PARSER_VERSION:
            return ProviderResult(
                suggestions=[],
                hints=FunctionHints(
                    state=FunctionsState.OUTDATED_PARSER,
                    parser_version=parser_version,
                ),
            )
        functions = project.get("functions") or {}
        if not functions:
            return ProviderResult(
                suggestions=[],
                hints=FunctionHints(state=FunctionsState.NO_FUNCTIONS),
            )
        return ProviderResult(
            suggestions=_build_suggestions(project),
            hints=FunctionHints(
                state=FunctionsState.OK,
                function_types_found=sorted(
                    {function["function_type"] for function in functions.values()}
                ),
            ),
        )
