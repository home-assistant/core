"""Models for AVM FRITZ!Box."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import NotRequired, TypedDict

from homeassistant.util import dt as dt_util

from .const import MeshRoles


@dataclass
class Device:
    """FRITZ!Box device class."""

    connected: bool
    connected_to: str
    connection_type: str
    ip_address: str
    name: str
    ssid: str | None
    wan_access: bool | None = None


class Interface(TypedDict):
    """Interface details."""

    device: str
    mac: str
    op_mode: str
    ssid: str | None
    type: str


HostAttributes = TypedDict(
    "HostAttributes",
    {
        "Index": int,
        "IPAddress": str,
        "MACAddress": str,
        "Active": bool,
        "HostName": str,
        "InterfaceType": str,
        "X_AVM-DE_Port": int,
        "X_AVM-DE_Speed": int,
        "X_AVM-DE_UpdateAvailable": bool,
        "X_AVM-DE_UpdateSuccessful": str,
        "X_AVM-DE_InfoURL": str | None,
        "X_AVM-DE_MACAddressList": str | None,
        "X_AVM-DE_Model": str | None,
        "X_AVM-DE_URL": str | None,
        "X_AVM-DE_Guest": bool,
        "X_AVM-DE_RequestClient": str,
        "X_AVM-DE_VPN": bool,
        "X_AVM-DE_WANAccess": NotRequired[str],
        "X_AVM-DE_Disallow": bool,
        "X_AVM-DE_IsMeshable": str,
        "X_AVM-DE_Priority": str,
        "X_AVM-DE_FriendlyName": str,
        "X_AVM-DE_FriendlyNameIsWriteable": str,
    },
)


class HostInfo(TypedDict):
    """FRITZ!Box host info class."""

    mac: str
    name: str
    ip: str
    status: bool


class FritzDevice:
    """Representation of a device connected to the FRITZ!Box."""

    def __init__(self, mac: str, name: str) -> None:
        """Initialize device info."""
        self._connected = False
        self._connected_to: str | None = None
        self._connection_type: str | None = None
        self._ip_address: str | None = None
        self._last_activity: datetime | None = None
        self._mac = mac
        self._name = name
        self._ssid: str | None = None
        self._wan_access: bool | None = False

    def update(self, dev_info: Device, consider_home: float) -> None:
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()

        if self._last_activity:
            consider_home_evaluated = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
        else:
            consider_home_evaluated = dev_info.connected

        if not self._name:
            self._name = dev_info.name or self._mac.replace(":", "_")

        self._connected = dev_info.connected or consider_home_evaluated

        if dev_info.connected:
            self._last_activity = utc_point_in_time

        self._connected_to = dev_info.connected_to
        self._connection_type = dev_info.connection_type
        self._ip_address = dev_info.ip_address
        self._ssid = dev_info.ssid
        self._wan_access = dev_info.wan_access

    @property
    def connected_to(self) -> str | None:
        """Return connected status."""
        return self._connected_to

    @property
    def connection_type(self) -> str | None:
        """Return connected status."""
        return self._connection_type

    @property
    def is_connected(self) -> bool:
        """Return connected status."""
        return self._connected

    @property
    def mac_address(self) -> str:
        """Get MAC address."""
        return self._mac

    @property
    def hostname(self) -> str:
        """Get Name."""
        return self._name

    @property
    def ip_address(self) -> str | None:
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    def ssid(self) -> str | None:
        """Return device connected SSID."""
        return self._ssid

    @property
    def wan_access(self) -> bool | None:
        """Return device wan access."""
        return self._wan_access


class SwitchInfo(TypedDict):
    """FRITZ!Box switch info class."""

    description: str
    friendly_name: str
    icon: str
    type: str
    callback_update: Callable
    callback_switch: Callable
    init_state: bool


@dataclass
class ConnectionInfo:
    """Fritz sensor connection information class."""

    connection: str
    mesh_role: MeshRoles
    wan_enabled: bool
    ipv6_active: bool
