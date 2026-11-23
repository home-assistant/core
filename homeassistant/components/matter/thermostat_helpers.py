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
from matter_server.common.helpers.util import (
    create_attribute_path_from_attribute,
    parse_value,
)

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .const import DOMAIN

if TYPE_CHECKING:
    from matter_server.client import MatterClient
    from matter_server.client.models.node import MatterEndpoint

_Status = clusters.Globals.Enums.status
_PresetTypeFeature = clusters.Thermostat.Bitmaps.PresetTypeFeaturesBitmap
_ThermostatFeature = clusters.Thermostat.Bitmaps.Feature
_PresetScenario = clusters.Thermostat.Enums.PresetScenarioEnum
_PresetStruct = clusters.Thermostat.Structs.PresetStruct
_PresetsType = clusters.Thermostat.Attributes.Presets.attribute_type.Type

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


class PresetsNotSupportedError(ServiceValidationError):
    """Thermostat does not support the Presets feature."""

    def __init__(self) -> None:
        """Initialize the error with a translated message."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="presets_not_supported",
        )


class PresetNotFoundError(ServiceValidationError):
    """Referenced preset handle no longer exists on the device."""

    def __init__(self) -> None:
        """Initialize the error with a translated message."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key="preset_not_found_on_device",
        )


class InvalidPresetDataError(ServiceValidationError):
    """The preset data is missing or outside what the thermostat accepts."""

    def __init__(
        self, translation_key: str, placeholders: dict[str, str] | None = None
    ) -> None:
        """Initialize the error with a translated message."""
        super().__init__(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )


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


def _ensure_presets_supported(endpoint: MatterEndpoint) -> None:
    """Raise if the endpoint does not advertise the Presets feature."""
    feature_map = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.FeatureMap)
        or 0
    )
    if not feature_map & _ThermostatFeature.kPresets:
        raise PresetsNotSupportedError


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


def _validate_setpoint(
    endpoint: MatterEndpoint,
    setpoint: int | None,
    min_attribute: type[clusters.ClusterAttributeDescriptor],
    max_attribute: type[clusters.ClusterAttributeDescriptor],
    translation_key: str,
) -> None:
    """Raise if `setpoint` is outside the thermostat's absolute limits."""
    if setpoint is None:
        return
    minimum = _normalize(endpoint.get_attribute_value(None, min_attribute))
    maximum = _normalize(endpoint.get_attribute_value(None, max_attribute))
    if (minimum is not None and setpoint < minimum) or (
        maximum is not None and setpoint > maximum
    ):
        raise InvalidPresetDataError(
            translation_key,
            {
                "min": "-" if minimum is None else str(minimum / 100),
                "max": "-" if maximum is None else str(maximum / 100),
            },
        )


def _validate_setpoints(
    endpoint: MatterEndpoint,
    heating_setpoint: int | None,
    cooling_setpoint: int | None,
) -> None:
    """Raise if a setpoint is outside the thermostat's absolute limits."""
    _validate_setpoint(
        endpoint,
        heating_setpoint,
        clusters.Thermostat.Attributes.AbsMinHeatSetpointLimit,
        clusters.Thermostat.Attributes.AbsMaxHeatSetpointLimit,
        "preset_heating_setpoint_out_of_range",
    )
    _validate_setpoint(
        endpoint,
        cooling_setpoint,
        clusters.Thermostat.Attributes.AbsMinCoolSetpointLimit,
        clusters.Thermostat.Attributes.AbsMaxCoolSetpointLimit,
        "preset_cooling_setpoint_out_of_range",
    )


def _validate_new_preset(
    endpoint: MatterEndpoint,
    preset_types: list[Any],
    preset_scenario: int,
    name: str | None,
    heating_setpoint: int | None,
    cooling_setpoint: int | None,
) -> None:
    """Raise if the device's write rules (§4.3.11.50) would refuse a new preset."""
    if preset_scenario == _PresetScenario.kUserDefined and not (name and name.strip()):
        raise InvalidPresetDataError("preset_name_required")
    feature_map = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.FeatureMap)
        or 0
    )
    if feature_map & _ThermostatFeature.kHeating and heating_setpoint is None:
        raise InvalidPresetDataError("preset_heating_setpoint_required")
    if feature_map & _ThermostatFeature.kCooling and cooling_setpoint is None:
        raise InvalidPresetDataError("preset_cooling_setpoint_required")
    preset_type = next(
        (pt for pt in preset_types if pt.presetScenario == preset_scenario), None
    )
    if preset_type is None:
        raise InvalidPresetDataError("preset_scenario_not_supported")
    current_presets = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.Presets) or []
    )
    max_presets = _normalize(
        endpoint.get_attribute_value(
            None, clusters.Thermostat.Attributes.NumberOfPresets
        )
    )
    if max_presets is not None and len(current_presets) >= max_presets:
        raise InvalidPresetDataError(
            "preset_limit_reached", {"limit": str(max_presets)}
        )
    scenario_count = sum(
        1 for preset in current_presets if preset.presetScenario == preset_scenario
    )
    if scenario_count >= preset_type.numberOfPresets:
        raise InvalidPresetDataError(
            "preset_scenario_limit_reached",
            {"limit": str(preset_type.numberOfPresets)},
        )
    _validate_setpoints(endpoint, heating_setpoint, cooling_setpoint)


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
    endpoint: MatterEndpoint,
    build_next: Callable[[list[Any]], list[Any]],
) -> None:
    """Replace the device's Presets list with the list `build_next` derives from it.

    The result is the full intended list, not a diff: per §4.3.11.50 a handle
    missing from it is a removal, and a preset with `presetHandle` null is an
    addition. `write_atomic_attribute` runs the AtomicRequest handshake, and
    the device still applies its own write rules. The write carries the
    cluster's data version from this read, so the device refuses it instead
    of silently overwriting a change made elsewhere since.
    """
    node = endpoint.node
    presets_path = create_attribute_path_from_attribute(
        endpoint_id=endpoint.endpoint_id,
        attribute=clusters.Thermostat.Attributes.Presets,
    )
    cluster_path = f"{endpoint.endpoint_id}/{clusters.Thermostat.id}"
    status: int | None = None
    for attempt in range(PRESET_WRITE_ATTEMPTS):
        report = await matter_client.read(node.node_id, [presets_path])
        data_version = (report.data_versions or {}).get(cluster_path)
        # The raw read is the wire format; decode it into PresetStruct entries.
        current_presets = cast(
            list[Any] | None,
            parse_value("presets", report.attributes.get(presets_path), _PresetsType),
        )
        if current_presets is None or data_version is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="presets_not_reported"
            )
        result = await matter_client.write_atomic_attribute(
            node_id=node.node_id,
            attribute_path=presets_path,
            value=build_next(current_presets),
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
    endpoint: MatterEndpoint,
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
    setpoint of None keeps the current value of an existing preset.
    """
    _ensure_presets_supported(endpoint)
    preset_types = (
        endpoint.get_attribute_value(None, clusters.Thermostat.Attributes.PresetTypes)
        or []
    )

    if preset_handle is None:
        if preset_scenario is None:
            raise InvalidPresetDataError("preset_scenario_required")
        _validate_new_preset(
            endpoint,
            preset_types,
            preset_scenario,
            name,
            heating_setpoint,
            cooling_setpoint,
        )
        new_preset = _PresetStruct(
            presetHandle=NullValue,
            presetScenario=preset_scenario,
            name=_resolve_name(preset_types, preset_scenario, name),
            coolingSetpoint=cooling_setpoint,
            heatingSetpoint=heating_setpoint,
            builtIn=False,
        )

        def build_add(current_presets: list[Any]) -> list[Any]:
            resolved_name = new_preset.name

            _validate_unique_preset_name(
                current_presets,
                preset_scenario,
                resolved_name,
            )

            return [*current_presets, new_preset]

        await _write_presets(matter_client, endpoint, build_add)
        return

    _validate_setpoints(endpoint, heating_setpoint, cooling_setpoint)

    def build_next(current_presets: list[Any]) -> list[Any]:
        for preset in current_presets:
            if preset.presetHandle == preset_handle:
                break
        else:
            raise PresetNotFoundError

        current_name = _normalize(preset.name)
        resolved_name = _resolve_name(preset_types, preset.presetScenario, name)
        if resolved_name is None:
            resolved_name = current_name

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

        if _normalize(edited_preset.name) != current_name:
            _validate_unique_preset_name(
                current_presets,
                edited_preset.presetScenario,
                edited_preset.name,
                exclude_handle=preset_handle,
            )

        return [
            edited_preset if preset.presetHandle == preset_handle else preset
            for preset in current_presets
        ]

    await _write_presets(matter_client, endpoint, build_next)


def _validate_unique_preset_name(
    current_presets: list[Any],
    scenario: int,
    name: str | None,
    exclude_handle: bytes | None = None,
) -> None:
    """Ensure preset names are unique within their scenario."""
    normalized_name = _normalize(name)

    for preset in current_presets:
        if _normalize(preset.presetScenario) != _normalize(scenario):
            continue

        if exclude_handle is not None and preset.presetHandle == exclude_handle:
            continue

        if _normalize(preset.name) == normalized_name:
            raise InvalidPresetDataError("preset_name_not_unique")


async def remove_thermostat_preset(
    matter_client: MatterClient,
    endpoint: MatterEndpoint,
    preset_handle: bytes,
) -> None:
    """Remove a preset from the thermostat.

    A preset that a schedule references is refused by the device's own write
    rules (§4.3.11.50).
    """
    _ensure_presets_supported(endpoint)

    def build_next(current_presets: list[Any]) -> list[Any]:
        if not any(preset.presetHandle == preset_handle for preset in current_presets):
            raise PresetNotFoundError
        return [
            preset for preset in current_presets if preset.presetHandle != preset_handle
        ]

    await _write_presets(matter_client, endpoint, build_next)
