"""Models for the Thread integration."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import voluptuous as vol


class ThreadState(Enum):
    """The platform state of an entity."""

    DISABLED = 0
    DETACHED = 1
    CHILD = 2
    ROUTER = 3
    LEADER = 4


@dataclass
class Timestamp:
    """Operational dataset."""

    SCHEMA = vol.Schema(
        {
            vol.Optional("Authoritative"): bool,
            vol.Optional("Seconds"): int,
            vol.Optional("Ticks"): int,
        }
    )

    authoritative: bool | None = None
    seconds: int | None = None
    ticks: int | None = None

    def as_json(self) -> dict:
        """Serialize to JSON."""
        result: dict[str, Any] = {}
        if self.authoritative is not None:
            result["Authoritative"] = self.authoritative
        if self.seconds is not None:
            result["Seconds"] = self.seconds
        if self.ticks is not None:
            result["Ticks"] = self.ticks
        return result

    @classmethod
    def from_json(cls, json_data: Any) -> Timestamp:
        """Deserialize from JSON."""
        cls.SCHEMA(json_data)
        return cls(
            json_data.get("Authoritative"),
            json_data.get("Seconds"),
            json_data.get("Ticks"),
        )


@dataclass
class SecurityPolicy:
    """Security policy."""

    SCHEMA = vol.Schema(
        {
            vol.Optional("AutonomousEnrollment"): bool,
            vol.Optional("CommercialCommissioning"): bool,
            vol.Optional("ExternalCommissioning"): bool,
            vol.Optional("NativeCommissioning"): bool,
            vol.Optional("NetworkKeyProvisioning"): bool,
            vol.Optional("NonCcmRouters"): bool,
            vol.Optional("ObtainNetworkKey"): bool,
            vol.Optional("RotationTime"): int,
            vol.Optional("Routers"): bool,
            vol.Optional("TobleLink"): bool,
        }
    )

    autonomous_enrollment: bool | None = None
    commercial_commissioning: bool | None = None
    external_commissioning: bool | None = None
    native_commissioning: bool | None = None
    network_key_provisioning: bool | None = None
    non_ccm_routers: bool | None = None
    obtain_network_key: bool | None = None
    rotation_time: int | None = None
    routers: bool | None = None
    to_ble_link: bool | None = None

    def as_json(self) -> dict:
        """Serialize to JSON."""
        result: dict[str, Any] = {}
        if self.autonomous_enrollment is not None:
            result["AutonomousEnrollment"] = self.autonomous_enrollment
        if self.commercial_commissioning is not None:
            result["CommercialCommissioning"] = self.commercial_commissioning
        if self.external_commissioning is not None:
            result["ExternalCommissioning"] = self.external_commissioning
        if self.native_commissioning is not None:
            result["NativeCommissioning"] = self.native_commissioning
        if self.network_key_provisioning is not None:
            result["NetworkKeyProvisioning"] = self.network_key_provisioning
        if self.non_ccm_routers is not None:
            result["NonCcmRouters"] = self.non_ccm_routers
        if self.obtain_network_key is not None:
            result["ObtainNetworkKey"] = self.obtain_network_key
        if self.rotation_time is not None:
            result["RotationTime"] = self.rotation_time
        if self.routers is not None:
            result["Routers"] = self.routers
        if self.to_ble_link is not None:
            result["TobleLink"] = self.to_ble_link
        return result

    @classmethod
    def from_json(cls, json_data: Any) -> SecurityPolicy:
        """Deserialize from JSON."""
        cls.SCHEMA(json_data)
        return cls(
            json_data.get("AutonomousEnrollment"),
            json_data.get("CommercialCommissioning"),
            json_data.get("ExternalCommissioning"),
            json_data.get("NativeCommissioning"),
            json_data.get("NetworkKeyProvisioning"),
            json_data.get("NonCcmRouters"),
            json_data.get("ObtainNetworkKey"),
            json_data.get("RotationTime"),
            json_data.get("Routers"),
            json_data.get("TobleLink"),
        )


@dataclass()
class OperationalDataSet:
    """Operational dataset."""

    SCHEMA = vol.Schema(
        {
            vol.Optional("ActiveTimestamp"): dict,
            vol.Optional("ChannelMask"): int,
            vol.Optional("Channel"): int,
            vol.Optional("Delay"): int,
            vol.Optional("ExtPanId"): str,
            vol.Optional("MeshLocalPrefix"): str,
            vol.Optional("NetworkKey"): str,
            vol.Optional("NetworkName"): str,
            vol.Optional("PanId"): int,
            vol.Optional("PendingTimestamp"): dict,
            vol.Optional("PSKc"): str,
            vol.Optional("SecurityPolicy"): dict,
        }
    )

    active_timestamp: Timestamp | None = None
    channel_mask: int | None = None
    channel: int | None = None
    delay: int | None = None
    extended_pan_id: str | None = None
    mesh_local_prefix: str | None = None
    network_key: str | None = None
    network_name: str | None = None
    pan_id: int | None = None
    pending_timestamp: Timestamp | None = None
    psk_c: str | None = None
    security_policy: SecurityPolicy | None = None

    def as_json(self) -> dict:
        """Serialize to JSON."""
        result: dict[str, Any] = {}
        if self.active_timestamp is not None:
            result["ActiveTimestamp"] = self.active_timestamp.as_json()
        if self.channel_mask is not None:
            result["ChannelMask"] = self.channel_mask
        if self.channel is not None:
            result["Channel"] = self.channel
        if self.delay is not None:
            result["Delay"] = self.delay
        if self.extended_pan_id is not None:
            result["ExtPanId"] = self.extended_pan_id
        if self.mesh_local_prefix is not None:
            result["MeshLocalPrefix"] = self.mesh_local_prefix
        if self.network_key is not None:
            result["NetworkKey"] = self.network_key
        if self.network_name is not None:
            result["NetworkName"] = self.network_name
        if self.pan_id is not None:
            result["PanId"] = self.pan_id
        if self.pending_timestamp is not None:
            result["PendingTimestamp"] = self.pending_timestamp.as_json()
        if self.psk_c is not None:
            result["PSKc"] = self.psk_c
        if self.security_policy is not None:
            result["SecurityPolicy"] = self.security_policy.as_json()
        return result

    @classmethod
    def from_json(cls, json_data: Any) -> OperationalDataSet:
        """Deserialize from JSON."""
        cls.SCHEMA(json_data)
        active_timestamp = None
        pending_timestamp = None
        security_policy = None
        if "ActiveTimestamp" in json_data:
            active_timestamp = Timestamp.from_json(json_data["ActiveTimestamp"])
        if "PendingTimestamp" in json_data:
            pending_timestamp = Timestamp.from_json(json_data["PendingTimestamp"])
        if "SecurityPolicy" in json_data:
            security_policy = SecurityPolicy.from_json(json_data["SecurityPolicy"])

        return OperationalDataSet(
            active_timestamp,
            json_data.get("ChannelMask"),
            json_data.get("Channel"),
            json_data.get("Delay"),
            json_data.get("ExtPanId"),
            json_data.get("MeshLocalPrefix"),
            json_data.get("NetworkKey"),
            json_data.get("NetworkName"),
            json_data.get("PanId"),
            pending_timestamp,
            json_data.get("PSKc"),
            security_policy,
        )
