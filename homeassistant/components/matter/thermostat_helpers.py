"""Thermostat cluster helpers for the Matter integration.

Currently covers preset management: creating, editing and removing entries in
the Thermostat cluster's Presets attribute, which may only be written inside
an atomic write (Matter 1.4 spec §7.15 "Atomic Request"). The server runs that
handshake, and the device's own write rules (§4.3.11.50), behind
`write_atomic_attribute`.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

from chip.clusters import Objects as clusters
from chip.clusters.Types import NullValue
from matter_server.common.helpers.util import create_attribute_path_from_attribute

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint, MatterNode

_Status = clusters.Globals.Enums.status
_PresetTypeFeature = clusters.Thermostat.Bitmaps.PresetTypeFeaturesBitmap
_PresetScenario = clusters.Thermostat.Enums.PresetScenarioEnum
_PresetStruct = clusters.Thermostat.Structs.PresetStruct

# A DATA_VERSION_MISMATCH mostly comes from another attribute of the cluster
# changing, such as the measured temperature, so a retried read usually
# succeeds; this is the write-server's own retry count for that case.
PRESET_WRITE_ATTEMPTS = 2

# What a rejected preset write means for the user, for the statuses that
# the device returns for a reason other than our own request shape.
_PRESET_WRITE_HINTS: dict[int, str] = {
    _Status.kDataVersionMismatch: "preset_write_data_version_mismatch",
    _Status.kBusy: "preset_write_busy",
    _Status.kInvalidInState: "preset_write_invalid_in_state",
}


class ThermostatEndpointNotFoundError(HomeAssistantError):
    """No endpoint on this node implements the Thermostat cluster."""


class PresetsNotSupportedError(ServiceValidationError):
    """Thermostat does not support the Presets feature."""


class PresetNotFoundError(ServiceValidationError):
    """Referenced preset handle no longer exists on the device."""


class InvalidPresetDataError(ServiceValidationError):
    """A required argument for this preset operation is missing."""


class PresetWriteRejectedError(HomeAssistantError):
    """The device rejected a Presets write; `status` is its Matter status."""

    def __init__(self, status: int) -> None:
        """Translate the device's status into a HomeAssistantError."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=_PRESET_WRITE_HINTS.get(status, "preset_write_failed"),
            translation_placeholders={"status": str(status)},
        )
        self.status = status


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


def _write_error_status(result: Any) -> int | None:
    """Return the first unsuccessful Matter status of a write response, if any.

    A write is answered with a list of per-path results rather than an error,
    so a device rejecting the write otherwise looks like a successful call.
    """
    if not isinstance(result, list):
        return None
    for item in result:
        status: int | None = item.get("Status") if isinstance(item, dict) else None
        if status:
            return status
    return None


async def _write_presets(
    matter_client: MatterClient,
    node: MatterNode,
    endpoint: MatterEndpoint,
    build_next: Callable[[list[Any]], list[Any]],
) -> None:
    """Replace the device's Presets list with the list `build_next` derives from it.

    The result is the full intended list, not a diff: per §4.3.11.50 a handle
    missing from it is a removal, and a preset with `presetHandle` null is an
    addition. `write_atomic_attribute` runs the AtomicRequest handshake and
    the device's own write-rule validation (built-in/active/schedule
    protection on removal, name uniqueness, per-scenario limits); this helper
    no longer duplicates those rules. The write carries the cluster's data
    version from this read, so the device refuses it instead of silently
    overwriting a change made elsewhere since.
    """
    presets_path = create_attribute_path_from_attribute(
        endpoint_id=endpoint.endpoint_id,
        attribute=clusters.Thermostat.Attributes.Presets,
    )
    cluster_path = f"{endpoint.endpoint_id}/{clusters.Thermostat.id}"
    status: int | None = None
    for attempt in range(PRESET_WRITE_ATTEMPTS):
        report = await matter_client.read(node.node_id, [presets_path])
        current_presets = report.attributes.get(presets_path)
        data_version = (report.data_versions or {}).get(cluster_path)
        if current_presets is None or data_version is None:
            raise HomeAssistantError("The device did not report its presets")
        # write_atomic_attribute ships in matter-python-client after 1.5.5; drop
        # this ignore once the requirement is bumped past that.
        result = await matter_client.write_atomic_attribute(  # type: ignore[attr-defined]
            node_id=node.node_id,
            attribute_path=presets_path,
            value=build_next(cast(list[Any], current_presets)),
            data_version=data_version,
        )
        status = _write_error_status(result)
        if (
            status != _Status.kDataVersionMismatch
            or attempt == PRESET_WRITE_ATTEMPTS - 1
        ):
            break
    if status is not None:
        raise PresetWriteRejectedError(status)


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
            resolved_name = _resolve_name(preset_types, preset_scenario, name)
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
    """Remove a preset from the thermostat.

    Built-in, active, or schedule-referenced presets are rejected by the
    device's own write rules (§4.3.11.50) rather than checked here.
    """
    endpoint = _get_thermostat_endpoint_or_raise(node)
    _ensure_presets_supported(endpoint)

    def build_next(current_presets: list[Any]) -> list[Any]:
        if not any(preset.presetHandle == preset_handle for preset in current_presets):
            raise PresetNotFoundError("The preset no longer exists on the device")
        return [
            preset for preset in current_presets if preset.presetHandle != preset_handle
        ]

    await _write_presets(matter_client, node, endpoint, build_next)
