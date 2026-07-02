"""Helper utilities for ZHA Infrared."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zigpy.types.named import EUI64

from homeassistant.components.zha.helpers import get_zha_gateway_proxy
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.yaml import load_yaml

from .const import BUILTIN_PROFILE_FILE, LOCAL_PROFILE_FILE


@dataclass(slots=True)
class DeviceMatchRule:
    """Matching rules for profile-to-device resolution."""

    models: set[str]
    manufacturers: set[str]
    device_types: set[int]
    required_in_clusters: set[int]


@dataclass(slots=True)
class TransportSpec:
    """Cluster transport definition for IR send operations."""

    cluster_id: int
    command_id: int
    command_arg: str
    expect_reply: bool


@dataclass(slots=True)
class CodecSpec:
    """Codec definition used to build device payload."""

    name: str


@dataclass(slots=True)
class ProfileFeatures:
    """Capability switches declared by the profile."""

    send_ir: bool
    receive_ir: bool


@dataclass(slots=True)
class ReceiveArmCommandSpec:
    """Generic command used to arm a receiver before reading signals."""

    call_command_id: int
    call_arg: str
    call_value: Any
    state_cluster_id: int
    state_attribute: str
    state_armed_value: Any
    state_disarmed_value: Any | None
    min_command_interval_seconds: int
    repeat_interval_seconds: int
    reset_interval_on_update: bool
    reset_on_arm_value: bool


@dataclass(slots=True)
class ReceiveSpec:
    """Receive transport configuration for profile-driven receivers."""

    method: str
    attribute: str
    poll_interval_seconds: int
    arm_command: ReceiveArmCommandSpec | None


@dataclass(slots=True)
class DeviceProfile:
    """Full manifest profile for a specific family of devices."""

    profile_id: str
    name: str
    match: DeviceMatchRule
    features: ProfileFeatures
    transport: TransportSpec
    codec: CodecSpec
    receive: ReceiveSpec | None


@dataclass(slots=True)
class SupportedDevice:
    """Runtime mapping of a discovered endpoint to a profile."""

    name: str
    ieee: str
    endpoint_id: int
    profile: DeviceProfile


def get_supported_devices(hass: HomeAssistant) -> list[SupportedDevice]:
    """Resolve supported Zigbee IR endpoints using manifest-driven profiles."""
    try:
        gateway_proxy = get_zha_gateway_proxy(hass)
    except ValueError:
        return []

    profiles = _load_profiles(hass)
    devices: list[SupportedDevice] = []
    for proxy in gateway_proxy.device_proxies.values():
        device = proxy.device
        model = device.model or ""
        manufacturer = device.manufacturer or ""
        name = device.name or f"Device {device.ieee}"
        ieee = str(device.ieee)

        for endpoint_id, endpoint in device.device.endpoints.items():
            if endpoint_id == 0:
                continue

            in_clusters = set(endpoint.in_clusters)
            for profile in profiles:
                if not _matches_profile(
                    profile=profile,
                    model=model,
                    manufacturer=manufacturer,
                    device_type=endpoint.device_type,
                    in_clusters=in_clusters,
                ):
                    continue

                devices.append(
                    SupportedDevice(
                        name=name,
                        ieee=ieee,
                        endpoint_id=endpoint_id,
                        profile=profile,
                    )
                )
                break

    return sorted(
        devices,
        key=lambda item: (
            item.name.casefold(),
            item.profile.profile_id,
            item.ieee,
            item.endpoint_id,
        ),
    )


def get_ir_cluster(hass: HomeAssistant, device: SupportedDevice) -> Any | None:
    """Resolve transport cluster for a configured supported device."""
    return get_cluster_by_id(hass, device, device.profile.transport.cluster_id)


def get_cluster_by_id(
    hass: HomeAssistant, device: SupportedDevice, cluster_id: int
) -> Any | None:
    """Resolve endpoint in-cluster by id for a supported device."""
    try:
        gateway_proxy = get_zha_gateway_proxy(hass)
    except ValueError:
        return None

    device_proxy = gateway_proxy.get_device_proxy(EUI64.convert(device.ieee))
    if device_proxy is None:
        return None

    endpoint = device_proxy.device.device.endpoints.get(device.endpoint_id)
    if endpoint is None:
        return None

    return endpoint.in_clusters.get(cluster_id)


def get_receive_spec(profile: DeviceProfile) -> ReceiveSpec | None:
    """Return receive configuration for profiles that support receiving."""
    return profile.receive


def _matches_profile(
    profile: DeviceProfile,
    model: str,
    manufacturer: str,
    device_type: int | None,
    in_clusters: set[int],
) -> bool:
    match = profile.match
    if match.models and model not in match.models:
        return False
    if match.manufacturers and manufacturer not in match.manufacturers:
        return False
    if match.device_types and device_type not in match.device_types:
        return False
    if not match.required_in_clusters.issubset(in_clusters):
        return False
    return True


def _load_profiles(hass: HomeAssistant) -> list[DeviceProfile]:
    """Load bundled profiles and merge optional local overrides from HA config."""
    bundled_path = Path(__file__).with_name(BUILTIN_PROFILE_FILE)
    bundled_raw = _load_yaml_list_file(bundled_path)
    merged_raw = list(bundled_raw)

    local_yaml_path = Path(hass.config.path(LOCAL_PROFILE_FILE))
    local_yaml_raw = _load_yaml_list_file(local_yaml_path)
    if local_yaml_raw:
        merged_raw.extend(local_yaml_raw)

    profiles: list[DeviceProfile] = []
    for item in merged_raw:
        profile = _parse_profile(item)
        if profile.features.send_ir or profile.features.receive_ir:
            profiles.append(profile)
    return profiles


def _load_yaml_list_file(path: Path) -> list[dict[str, Any]]:
    """Load YAML profile list from disk, returning empty list on errors."""
    if not path.exists():
        return []
    try:
        data = load_yaml(path)
    except (HomeAssistantError, OSError):
        return []
    if data is None:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _parse_profile(raw: dict[str, Any]) -> DeviceProfile:
    """Normalize raw profile mapping into strongly typed objects."""
    match_raw = raw.get("match", {})
    transport_raw = raw.get("transport", {})
    features_raw = raw.get("features", {})
    codec_raw = raw.get("codec", {})
    receive_raw = raw.get("receive", {})

    return DeviceProfile(
        profile_id=str(raw.get("id", "unknown")),
        name=str(raw.get("name", "Unnamed profile")),
        match=DeviceMatchRule(
            models={str(item) for item in match_raw.get("models", [])},
            manufacturers={
                str(item) for item in match_raw.get("manufacturers", [])
            },
            device_types={
                _parse_int_value(item) for item in match_raw.get("device_types", [])
            },
            required_in_clusters={
                _parse_int_value(item)
                for item in match_raw.get("required_in_clusters", [])
            },
        ),
        features=ProfileFeatures(
            send_ir=bool(features_raw.get("send_ir", True)),
            receive_ir=bool(features_raw.get("receive_ir", False)),
        ),
        transport=TransportSpec(
            cluster_id=_parse_int_value(transport_raw.get("cluster_id", 0)),
            command_id=_parse_int_value(transport_raw.get("command_id", 0)),
            command_arg=str(transport_raw.get("command_arg", "code")),
            expect_reply=bool(transport_raw.get("expect_reply", True)),
        ),
        codec=CodecSpec(
            name=str(codec_raw.get("name", "tuya_base64_rawtimings_v1")),
        ),
        receive=_parse_receive_spec(receive_raw, features_raw),
    )


def _parse_int_value(value: Any) -> int:
    """Parse integer values supporting decimal and hex-string forms."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    return int(value or 0)


def _parse_receive_spec(
    receive_raw: dict[str, Any], features_raw: dict[str, Any]
) -> ReceiveSpec | None:
    """Parse optional receive behavior from manifest profile."""
    if not bool(features_raw.get("receive_ir", False)):
        return None

    method = str(receive_raw.get("method", "cluster_attribute_read"))
    attribute = str(receive_raw.get("attribute", "last_learned_ir_code"))
    poll_interval_seconds = int(receive_raw.get("poll_interval_seconds", 1))
    arm_command = _parse_receive_arm_command_spec(receive_raw)
    return ReceiveSpec(
        method=method,
        attribute=attribute,
        poll_interval_seconds=max(1, poll_interval_seconds),
        arm_command=arm_command,
    )


def _parse_receive_arm_command_spec(
    receive_raw: dict[str, Any],
) -> ReceiveArmCommandSpec | None:
    """Parse optional generic arm command configuration."""
    arm_raw = receive_raw.get("arm_command")
    if not isinstance(arm_raw, dict):
        return None
    call_raw = arm_raw.get("call_cmd")
    state_raw = arm_raw.get("state_cmd")
    if not isinstance(call_raw, dict) or not isinstance(state_raw, dict):
        return None
    command_id_raw = call_raw.get("command_id")
    if command_id_raw is None:
        return None
    state_cluster_id_raw = state_raw.get("cluster_id")
    state_attribute_raw = state_raw.get("attribute")
    if state_cluster_id_raw is None or state_attribute_raw is None:
        return None

    reset_raw = arm_raw.get("reset", {})
    if not isinstance(reset_raw, dict):
        reset_raw = {}

    return ReceiveArmCommandSpec(
        call_command_id=_parse_int_value(command_id_raw),
        call_arg=str(call_raw.get("arg", "on_off")),
        call_value=call_raw.get("value", True),
        state_cluster_id=_parse_int_value(state_cluster_id_raw),
        state_attribute=str(state_attribute_raw),
        state_armed_value=state_raw.get("armed", True),
        state_disarmed_value=state_raw.get("disarmed"),
        min_command_interval_seconds=max(
            1, int(arm_raw.get("min_cmd_interval", 2))
        ),
        repeat_interval_seconds=max(
            1, int(arm_raw.get("repeat", 30))
        ),
        reset_interval_on_update=bool(reset_raw.get("on_receive", True)),
        reset_on_arm_value=bool(reset_raw.get("on_not_armed", False)),
    )
