"""Entity suggestions from the building functions of project data.

A function of a room or other space (switchable light, dimmable light, sun
protection, heating, socket, ...) has a type from the KNX master data and links
group addresses in roles - the function points of its type. Most projects have
functions, while KNX Information Model semantics of channels are still rare.

The role stored with a group address is used when it is one of the function
type; other group addresses get the first free function point of their DPT.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final, Literal, Required, TypedDict, override

import probatio
from xknxproject.models import DPTType, Function, KNXProject, Space

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from ..const import CONF_GA_PASSIVE
from ..entity_store_schema import KNX_SCHEMA_FOR_PLATFORM
from .base import SuggestionProvider
from .const import (
    PlatformSuggestion,
    ProviderResult,
    ProviderSuggestion,
    SuggestedGroupAddress,
)

if TYPE_CHECKING:
    from ...knx_module import KNXModule

type GaSlot = Literal["write", "state"]
# role -> config path and slots of its group address
type RoleConfig = dict[str, tuple[tuple[str, ...], tuple[GaSlot, ...]]]

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


@dataclass(frozen=True)
class FunctionEntity:
    """The entity of a function type: its platform and the config key of each role.

    Roles not listed are not used. All `required` roles have to be linked.
    """

    platform: Platform
    roles: RoleConfig
    required: tuple[str, ...]


_SWITCH_ROLES: Final[RoleConfig] = {
    "SwitchOnOff": (("ga_switch",), ("write",)),
    "InfoOnOff": (("ga_switch",), ("state",)),
}
_COVER_ROLES: Final[RoleConfig] = {
    "MoveUpDown": (("ga_up_down",), ("write",)),
    "StopStepUpDown": (("ga_step",), ("write",)),
    "CurrentAbsolutePositionBlindsPercentage": (("ga_position_state",), ("state",)),
    "CurrentAbsolutePositionSlatPercentage": (("ga_angle",), ("state",)),
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
    Platform.CLIMATE, _CLIMATE_ROLES, ("TempRoomSetpoint", "TempRoom")
)

FUNCTION_ENTITIES: Final[dict[str, FunctionEntity]] = {
    "FT-1": FunctionEntity(Platform.LIGHT, _SWITCH_ROLES, ("SwitchOnOff",)),
    # relative dimming is no brightness of a light entity
    "FT-2": FunctionEntity(Platform.LIGHT, _SWITCH_ROLES, ("SwitchOnOff",)),
    "FT-3": FunctionEntity(Platform.COVER, _COVER_ROLES, ("MoveUpDown",)),
    "FT-4": _CLIMATE,
    "FT-5": _CLIMATE,
    "FT-6": FunctionEntity(
        Platform.LIGHT,
        {
            **_SWITCH_ROLES,
            "DimmingValue": (("ga_brightness",), ("write",)),
            "InfoDimmingValue": (("ga_brightness",), ("state",)),
        },
        ("SwitchOnOff",),
    ),
    "FT-7": FunctionEntity(Platform.COVER, _COVER_ROLES, ("MoveUpDown",)),
    "FT-8": _CLIMATE,
    "FT-9": _CLIMATE,
    "FT-10": FunctionEntity(Platform.SWITCH, _SWITCH_ROLES, ("SwitchOnOff",)),
}


class FunctionsState(StrEnum):
    """Availability of building functions in the project data."""

    NO_PROJECT = "no_project"
    NO_FUNCTIONS = "no_functions"
    OK = "ok"


class FunctionHints(TypedDict, total=False):
    """Hints of the functions provider."""

    state: Required[FunctionsState]
    functions_found: int


def _function_roles(project: KNXProject, function: Function) -> dict[str, str]:
    """Map the roles of a function to the address of their group address.

    A stored role of the function type is kept. Other group addresses get the
    first free function point of their DPT, else of its main number; one
    without a DPT gets the first free point.
    """
    points = FUNCTION_POINTS.get(function["function_type"], ())
    names = {name for name, _dpt in points}
    roles: dict[str, str] = {}
    unassigned: list[str] = []
    for ref in function["group_addresses"].values():
        if ref["role"] in names and ref["role"] not in roles:
            roles[ref["role"]] = ref["address"]
        else:
            unassigned.append(ref["address"])

    def free(dpt: DPTType | None, exact: bool) -> str | None:
        for name, (main, sub) in points:
            if name in roles:
                continue
            if dpt is None or (
                dpt["main"] == main and (not exact or dpt["sub"] == sub)
            ):
                return name
        return None

    for address in unassigned:
        group_address = project["group_addresses"].get(address)
        dpt = group_address["dpt"] if group_address is not None else None
        if (role := free(dpt, exact=True) or free(dpt, exact=False)) is not None:
            roles[role] = address
    return roles


def _set_ga(config: dict[str, Any], path: tuple[str, ...], slot: str, ga: str) -> None:
    """Set a group address in a nested `knx` config."""
    for key in path:
        config = config.setdefault(key, {})
    config.setdefault(CONF_GA_PASSIVE, [])
    config[slot] = ga


def _build_platform_suggestion(
    project: KNXProject, function: Function
) -> tuple[Platform, PlatformSuggestion] | None:
    """Build the `knx` config of the entity a function becomes."""
    if (entity := FUNCTION_ENTITIES.get(function["function_type"])) is None:
        return None
    roles = _function_roles(project, function)
    if any(role not in roles for role in entity.required):
        return None
    knx_config: dict[str, Any] = {}
    used: set[str] = set()
    for role, (path, slots) in entity.roles.items():
        if (address := roles.get(role)) is None:
            continue
        for slot in slots:
            _set_ga(knx_config, path, slot, address)
        used.add(address)
    # the schema decides what a complete configuration needs
    try:
        KNX_SCHEMA_FOR_PLATFORM[entity.platform](knx_config)
    except probatio.Invalid:
        return None
    return entity.platform, PlatformSuggestion(
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
    suggestions: list[ProviderSuggestion] = []
    for function_id, function in (project.get("functions") or {}).items():
        if (built := _build_platform_suggestion(project, function)) is None:
            continue
        platform, platform_suggestion = built
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
                metadata={"function_type": function["function_type"]},
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
        functions = project.get("functions") or {}
        if not functions:
            return ProviderResult(
                suggestions=[],
                hints=FunctionHints(state=FunctionsState.NO_FUNCTIONS),
            )
        return ProviderResult(
            suggestions=_build_suggestions(project),
            hints=FunctionHints(
                state=FunctionsState.OK, functions_found=len(functions)
            ),
        )
