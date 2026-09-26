"""Data models for the Redfish integration."""

from dataclasses import dataclass
from typing import Any

STANDARD_RESET_TYPES = frozenset(
    {
        "ForceOff",
        "ForceOn",
        "ForceRestart",
        "FullPowerCycle",
        "GracefulRestart",
        "GracefulShutdown",
        "Nmi",
        "On",
        "Pause",
        "PowerCycle",
        "PushPowerButton",
        "Resume",
        "Suspend",
    }
)


@dataclass(frozen=True, slots=True)
class RedfishSystem:
    """A Redfish ComputerSystem resource."""

    odata_id: str
    system_id: str
    name: str | None
    uuid: str | None
    manufacturer: str | None
    model: str | None
    serial_number: str | None
    power_state: str | None
    reset_target: str | None
    reset_types: frozenset[str]


@dataclass(frozen=True, slots=True)
class RedfishData:
    """Data discovered from a Redfish service."""

    systems: dict[str, RedfishSystem]


def _non_empty_str(value: Any) -> str | None:
    """Return a non-empty string or None."""
    return value if isinstance(value, str) and value.strip() else None


def _reset_action(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Return the ComputerSystem reset action."""
    actions = payload.get("Actions")
    if not isinstance(actions, dict):
        return None
    reset = actions.get("#ComputerSystem.Reset")
    return reset if isinstance(reset, dict) else None


def get_reset_action_info_target(payload: dict[str, Any]) -> str | None:
    """Return the reset ActionInfo target."""
    if (reset := _reset_action(payload)) is None:
        return None
    return _non_empty_str(reset.get("@Redfish.ActionInfo"))


def parse_reset_action_info(payload: dict[str, Any]) -> frozenset[str]:
    """Parse reset types from an ActionInfo resource."""
    parameters = payload.get("Parameters")
    if not isinstance(parameters, list):
        return frozenset()
    for parameter in parameters:
        if not isinstance(parameter, dict) or parameter.get("Name") != "ResetType":
            continue
        allowable_values = parameter.get("AllowableValues")
        if not isinstance(allowable_values, list):
            return frozenset()
        return frozenset(
            value
            for value in allowable_values
            if isinstance(value, str) and value in STANDARD_RESET_TYPES
        )
    return frozenset()


def parse_system(payload: dict[str, Any]) -> RedfishSystem | None:
    """Parse a ComputerSystem resource, skipping unusable resources."""
    odata_id = _non_empty_str(payload.get("@odata.id"))
    system_id = _non_empty_str(payload.get("Id"))
    if odata_id is None or system_id is None:
        return None

    reset_target: str | None = None
    reset_types = frozenset[str]()
    if (reset := _reset_action(payload)) is not None and (
        reset_target := _non_empty_str(reset.get("target"))
    ):
        allowable_values = reset.get("ResetType@Redfish.AllowableValues")
        if isinstance(allowable_values, list):
            reset_types = frozenset(
                value
                for value in allowable_values
                if isinstance(value, str) and value in STANDARD_RESET_TYPES
            )

    return RedfishSystem(
        odata_id=odata_id,
        system_id=system_id,
        name=_non_empty_str(payload.get("Name")),
        uuid=_non_empty_str(payload.get("UUID")),
        manufacturer=_non_empty_str(payload.get("Manufacturer")),
        model=_non_empty_str(payload.get("Model")),
        serial_number=_non_empty_str(payload.get("SerialNumber")),
        power_state=_non_empty_str(payload.get("PowerState")),
        reset_target=reset_target,
        reset_types=reset_types,
    )
