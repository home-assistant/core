"""Models for AVM FRITZ!Box."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, NotRequired, TypedDict

from homeassistant.util import dt as dt_util

from .const import MeshRoles

# The mesh topology reports 255 when the signal strength is not available
INVALID_RCPI = 255


@dataclass(frozen=True)
class LinkInfo:
    """Mesh link details of a device connected to the FRITZ!Box."""

    signal_strength: int | None
    download_rate: int | None
    upload_rate: int | None
    max_download_rate: int | None
    max_upload_rate: int | None

    @classmethod
    def from_node_link(cls, node_link: dict[str, Any]) -> LinkInfo:
        """Create link details from a mesh topology node link."""
        rcpi = node_link.get("rx_rcpi")
        # rx/tx values are reported from the FRITZ!Box point of view
        return cls(
            signal_strength=None if rcpi == INVALID_RCPI else rcpi,
            download_rate=node_link.get("cur_data_rate_tx"),
            upload_rate=node_link.get("cur_data_rate_rx"),
            max_download_rate=node_link.get("max_data_rate_tx"),
            max_upload_rate=node_link.get("max_data_rate_rx"),
        )


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
    link_info: LinkInfo | None = None


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

    _connected: bool
    _connected_to: str
    _connection_type: str
    _ip_address: str
    _last_activity: datetime | None
    _link_info: LinkInfo | None
    _mac: str
    _name: str
    _ssid: str | None
    _wan_access: bool | None

    def __init__(self, mac: str, dev_info: Device, consider_home: float) -> None:
        """Initialize device info."""
        self._mac = mac
        self._last_activity = None
        self.update(dev_info, consider_home)

    def update(self, dev_info: Device, consider_home: float) -> None:
        """Update device info."""
        utc_point_in_time = dt_util.utcnow()

        if self._last_activity:
            consider_home_evaluated = (
                utc_point_in_time - self._last_activity
            ).total_seconds() < consider_home
        else:
            consider_home_evaluated = dev_info.connected

        self._name = dev_info.name or self._mac.replace(":", "_")

        self._connected = dev_info.connected or consider_home_evaluated

        if dev_info.connected:
            self._last_activity = utc_point_in_time

        self._connected_to = dev_info.connected_to
        self._connection_type = dev_info.connection_type
        self._ip_address = dev_info.ip_address
        self._link_info = dev_info.link_info
        self._ssid = dev_info.ssid
        self._wan_access = dev_info.wan_access

    @property
    def connected_to(self) -> str:
        """Return connected status."""
        return self._connected_to

    @property
    def connection_type(self) -> str:
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
    def ip_address(self) -> str:
        """Get IP address."""
        return self._ip_address

    @property
    def last_activity(self) -> datetime | None:
        """Return device last activity."""
        return self._last_activity

    @property
    def link_info(self) -> LinkInfo | None:
        """Return device mesh link details."""
        return self._link_info

    @property
    def ssid(self) -> str | None:
        """Return device connected SSID."""
        return self._ssid

    @property
    def wan_access(self) -> bool | None:
        """Return device wan access."""
        return self._wan_access

    @wan_access.setter
    def wan_access(self, allowed: bool) -> None:
        """Set device wan access."""
        self._wan_access = allowed


@dataclass
class ConnectionInfo:
    """Fritz sensor connection information class."""

    connection: str
    mesh_role: MeshRoles
    wan_enabled: bool
    ipv6_active: bool
    addon_infos_supported: bool
