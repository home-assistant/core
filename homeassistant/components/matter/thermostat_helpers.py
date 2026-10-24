"""Thermostat cluster helpers for the Matter integration.

Currently covers preset management: the atomic-write handshake required to
add, edit, or remove entries in the Thermostat cluster's Presets attribute
(Matter 1.4 spec §7.15 "Atomic Request" and §4.3.11.50 "Presets attribute
write rules").
"""

from collections.abc import Callable
import contextlib
from typing import TYPE_CHECKING, Any, cast

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import (
    THERMOSTAT_PRESET_ATOMIC_WRITE_TIMEOUT_MS,
    THERMOSTAT_PRESET_MIN_ATOMIC_WRITE_TIMEOUT_MS,
)

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

_AtomicRequestType = clusters.Globals.Enums.AtomicRequestTypeEnum
_Status = clusters.Globals.Enums.status
_PresetTypeFeature = clusters.Thermostat.Bitmaps.PresetTypeFeaturesBitmap
_PresetScenario = clusters.Thermostat.Enums.PresetScenarioEnum
_PresetStruct = clusters.Thermostat.Structs.PresetStruct

# A Timed Write transaction for the Presets write itself, distinct from the
# AtomicRequest window above (Matter spec §4.3.11.50 write rule 2).
THERMOSTAT_PRESET_TIMED_WRITE_TIMEOUT_MS = 3000


class ThermostatEndpointNotFoundError(HomeAssistantError):
    """No endpoint on this node implements the Thermostat cluster."""


class PresetsNotSupportedError(ServiceValidationError):
    """Thermostat does not support the Presets feature."""


class PresetNotFoundError(ServiceValidationError):
    """Referenced preset handle no longer exists on the device."""


class InvalidPresetDataError(ServiceValidationError):
    """Preset name, setpoints, or scenario fail device validation rules."""


class PresetInUseError(ServiceValidationError):
    """Preset cannot be removed because it is built-in, active, or scheduled."""


class AtomicWriteError(HomeAssistantError):
    """The atomic-write handshake for the Presets attribute failed."""


def _normalize[T](value: T) -> T | None:
    """Treat the Matter SDK's NullValue sentinel as None."""
    return None if value is NullValue else value


def _get_thermostat_endpoint_or_raise(node: MatterNode) -> MatterEndpoint:
    """Get the Thermostat endpoint from a node or raise an error."""
    for endpoint in node.endpoints.values():
        if endpoint.has_cluster(clusters.Thermostat):
            return endpoint
    raise ThermostatEndpointNotFoundError("No thermostat endpoint found on this device")


def _ensure_presets_supported(endpoint: MatterEndpoint) -> None:
    """Raise if the endpoint does not advertise the Presets feature."""
    feature_map = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.FeatureMap)
        or 0
    )
    if not feature_map & clusters.Thermostat.Bitmaps.Feature.kPresets:
        raise PresetsNotSupportedError("This thermostat does not support presets")


def _preset_type_supports_names(preset_types: list[Any], scenario: int) -> bool:
    """Return whether a preset of `scenario` may carry a Name."""
    return any(
        preset_type.presetScenario == scenario
        and preset_type.presetTypeFeatures & _PresetTypeFeature.kSupportsNames
        for preset_type in preset_types
    )


def _preset_type_limit(preset_types: list[Any], scenario: int) -> int | None:
    """Return the maximum number of presets allowed for `scenario`."""
    for preset_type in preset_types:
        if preset_type.presetScenario == scenario:
            return int(preset_type.numberOfPresets)
    return None


def _preset_name_conflict(
    current_presets: list[Any],
    scenario: int,
    name: str | None,
    except_handle: bytes | None,
) -> str | None:
    """Return why `name` cannot be used for a preset of `scenario`, or None.

    Names must be unique per scenario, a missing name included, and a
    UserDefined preset needs one (Matter spec §4.3.10.23.3, §4.3.10.17).
    """
    if scenario == _PresetScenario.kUserDefined and name is None:
        return "A user-defined preset needs a name"
    for preset in current_presets:
        if preset.presetHandle == except_handle:
            continue
        if preset.presetScenario != scenario:
            continue
        if _normalize(preset.name) != name:
            continue
        if name is None:
            return "Another preset of this scenario already has no name"
        return f'Another preset of this scenario is already named "{name}"'
    return None


def _preset_in_use(
    endpoint: MatterEndpoint,
    preset_handle: bytes,
) -> str | None:
    """Return why `preset_handle` cannot be removed, or None."""
    presets = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.Presets) or []
    )
    for preset in presets:
        if preset.presetHandle == preset_handle and _normalize(preset.builtIn) is True:
            return "Built-in presets cannot be removed"
    active_handle = endpoint.get_attribute_value(
        None, clusters.Thermostat.Attributes.ActivePresetHandle
    )
    if _normalize(active_handle) == preset_handle:
        return "The active preset cannot be removed"
    schedules = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.Schedules)
        or []
    )
    for schedule in schedules:
        if _normalize(schedule.presetHandle) == preset_handle:
            return "A schedule uses this preset"
        for transition in schedule.transitions:
            if _normalize(transition.presetHandle) == preset_handle:
                return "A schedule uses this preset"
    return None


def _describe_atomic_failure(
    response: clusters.Thermostat.Commands.AtomicResponse,
) -> str:
    """Format the most relevant status code of a failed AtomicResponse."""
    for status in response.attributeStatus:
        if status.statusCode != _Status.kSuccess:
            return f"{status.statusCode.name} ({status.statusCode})"
    return f"{response.statusCode.name} ({response.statusCode})"


async def _atomic_request(
    matter_client: MatterClient,
    node: MatterNode,
    endpoint_id: int,
    request_type: clusters.Globals.Enums.AtomicRequestTypeEnum,
    attribute_requests: list[int],
    timeout: int | None = None,
) -> clusters.Thermostat.Commands.AtomicResponse:
    """Send a Thermostat AtomicRequest command."""
    return await matter_client.send_device_command(
        node_id=node.node_id,
        endpoint_id=endpoint_id,
        command=clusters.Thermostat.Commands.AtomicRequest(
            requestType=request_type,
            attributeRequests=attribute_requests,
            timeout=timeout,
        ),
    )


def _ensure_write_window_long_enough(timeout: int | None) -> None:
    """Raise if the device granted a BeginWrite window that is too short to use."""
    if timeout is not None and timeout < THERMOSTAT_PRESET_MIN_ATOMIC_WRITE_TIMEOUT_MS:
        raise AtomicWriteError(
            f"The device allows only {timeout} ms to edit presets, "
            "too short to write them"
        )


def _require_reported_presets(
    live_values: dict[str, Any], presets_path: str
) -> list[Any]:
    """Return the live Presets value, or raise if the device did not report it."""
    current_presets = live_values.get(presets_path)
    if current_presets is None:
        raise AtomicWriteError("The device did not report its presets")
    return cast(list[Any], current_presets)


async def _write_presets(
    matter_client: MatterClient,
    node: MatterNode,
    endpoint: MatterEndpoint,
    build_next: Callable[[list[Any]], list[Any]],
) -> None:
    """Replace the device's Presets list with the list `build_next` derives from it.

    The result is the full intended list, not a diff: per §4.3.11.50 a handle
    missing from it is a removal, and a preset with `presetHandle` null is an
    addition. Presets may only be written inside the cluster's atomic-write
    handshake (§7.15.3): the current list is read from the device inside that
    window rather than from our (possibly stale) attribute cache, and the
    write itself is a Timed Write so other clients don't observe the pending
    list before it is committed.

    A window shorter than the required minimum is rolled back without
    writing (§7.15.1 step 1.2). A failed CommitWrite response already
    discards the pending write on the device (§7.15.6.4.2); any other
    failure after a successful BeginWrite, including one raised by
    `build_next`, is followed by a RollbackWrite.
    """
    presets_attribute_id = clusters.Thermostat.Attributes.Presets.attribute_id
    begin = await _atomic_request(
        matter_client,
        node,
        endpoint.endpoint_id,
        _AtomicRequestType.kBeginWrite,
        [presets_attribute_id],
        THERMOSTAT_PRESET_ATOMIC_WRITE_TIMEOUT_MS,
    )
    if begin.statusCode != _Status.kSuccess:
        raise AtomicWriteError(
            f"Could not start editing presets: {_describe_atomic_failure(begin)}"
        )

    atomic_attributes = [status.attributeID for status in begin.attributeStatus] or [
        presets_attribute_id
    ]

    try:
        _ensure_write_window_long_enough(begin.timeout)
        presets_path = create_attribute_path_from_attribute(
            endpoint_id=endpoint.endpoint_id,
            attribute=clusters.Thermostat.Attributes.Presets,
        )
        live_values = await matter_client.read_attribute(node.node_id, presets_path)
        current_presets = _require_reported_presets(live_values, presets_path)
        await matter_client.write_attribute(
            node_id=node.node_id,
            attribute_path=presets_path,
            value=build_next(current_presets),
            timed_request_timeout_ms=THERMOSTAT_PRESET_TIMED_WRITE_TIMEOUT_MS,
        )
        commit = await _atomic_request(
            matter_client,
            node,
            endpoint.endpoint_id,
            _AtomicRequestType.kCommitWrite,
            atomic_attributes,
        )
    except Exception:
        with contextlib.suppress(Exception):
            await _atomic_request(
                matter_client,
                node,
                endpoint.endpoint_id,
                _AtomicRequestType.kRollbackWrite,
                atomic_attributes,
            )
        raise

    if commit.statusCode != _Status.kSuccess:
        raise AtomicWriteError(
            f"Could not commit preset changes: {_describe_atomic_failure(commit)}"
        )


def _resolve_name(
    preset_types: list[Any],
    scenario: int,
    name: str | None,
) -> str | None:
    """Return the name to write for a preset of `scenario`.

    A name is dropped (not written as an explicit null) for a scenario that
    does not support names: the CHIP SDK treats an explicit null Name as set
    and the device rejects it for such a scenario.
    """
    if not _preset_type_supports_names(preset_types, scenario):
        return None
    return name.strip() if name and name.strip() else None


async def set_thermostat_preset(
    matter_client: MatterClient,
    node: MatterNode,
    *,
    preset_handle: bytes | None,
    preset_scenario: int | None,
    name: str | None,
    heating_setpoint: int | None,
    cooling_setpoint: int | None,
) -> None:
    """Add a new preset, or edit an existing one, on the thermostat.

    `preset_handle` is None to add a preset (then `preset_scenario` is
    required); otherwise it identifies the preset to edit, whose scenario
    and built-in flag are kept unchanged. Setpoints are in centidegrees; a
    setpoint of None keeps the preset's current value (new presets default
    to the fallback the caller passed in).
    """
    endpoint = _get_thermostat_endpoint_or_raise(node)
    _ensure_presets_supported(endpoint)
    preset_types = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.PresetTypes)
        or []
    )

    def build_next(current_presets: list[Any]) -> list[Any]:
        if preset_handle is None:
            if preset_scenario is None:
                raise InvalidPresetDataError(
                    "preset_scenario is required when adding a new preset"
                )
            limit = _preset_type_limit(preset_types, preset_scenario)
            existing_for_scenario = sum(
                1
                for preset in current_presets
                if preset.presetScenario == preset_scenario
            )
            if limit is not None and existing_for_scenario >= limit:
                raise InvalidPresetDataError(
                    "This device does not allow more presets of this scenario"
                )
            resolved_name = _resolve_name(preset_types, preset_scenario, name)
            conflict = _preset_name_conflict(
                current_presets, preset_scenario, resolved_name, None
            )
            if conflict is not None:
                raise InvalidPresetDataError(conflict)
            new_preset = _PresetStruct(
                presetHandle=NullValue,
                presetScenario=preset_scenario,
                name=resolved_name,
                coolingSetpoint=cooling_setpoint,
                heatingSetpoint=heating_setpoint,
                builtIn=False,
            )
            return [*current_presets, new_preset]

        for preset in current_presets:
            if preset.presetHandle == preset_handle:
                break
        else:
            raise PresetNotFoundError("The preset no longer exists on the device")

        resolved_name = _resolve_name(preset_types, preset.presetScenario, name)
        if resolved_name is None:
            resolved_name = _normalize(preset.name)
        conflict = _preset_name_conflict(
            current_presets, preset.presetScenario, resolved_name, preset_handle
        )
        if conflict is not None:
            raise InvalidPresetDataError(conflict)
        edited_preset = _PresetStruct(
            presetHandle=preset_handle,
            presetScenario=preset.presetScenario,
            name=resolved_name,
            coolingSetpoint=(
                cooling_setpoint
                if cooling_setpoint is not None
                else _normalize(preset.coolingSetpoint)
            ),
            heatingSetpoint=(
                heating_setpoint
                if heating_setpoint is not None
                else _normalize(preset.heatingSetpoint)
            ),
            builtIn=_normalize(preset.builtIn) is True,
        )
        return [
            edited_preset if preset.presetHandle == preset_handle else preset
            for preset in current_presets
        ]

    await _write_presets(matter_client, node, endpoint, build_next)


async def remove_thermostat_preset(
    matter_client: MatterClient,
    node: MatterNode,
    preset_handle: bytes,
) -> None:
    """Remove a preset from the thermostat."""
    endpoint = _get_thermostat_endpoint_or_raise(node)
    _ensure_presets_supported(endpoint)

    blocked_reason = _preset_in_use(endpoint, preset_handle)
    if blocked_reason is not None:
        raise PresetInUseError(blocked_reason)

    def build_next(current_presets: list[Any]) -> list[Any]:
        if not any(preset.presetHandle == preset_handle for preset in current_presets):
            raise PresetNotFoundError("The preset no longer exists on the device")
        return [
            preset for preset in current_presets if preset.presetHandle != preset_handle
        ]

    await _write_presets(matter_client, node, endpoint, build_next)
