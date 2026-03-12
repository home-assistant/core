"""Device models for the HiVi Speaker integration."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SyncGroupStatus(Enum):
    """Device type enumeration."""

    UNKNOWN = "unknown"
    MASTER = "master"  # Master speaker
    SLAVE = "slave"  # Slave speaker
    STANDALONE = "standalone"  # Standalone speaker (can be master or slave)


class ConnectionStatus(Enum):
    """Device status."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


class SlaveDeviceInfo(BaseModel):
    """Slave speaker information class."""

    friendly_name: str
    ssid: str
    mask: int | None
    volume: int
    mute: bool
    channel: int
    battery: int | None
    ip_addr: str
    version: str
    uuid: str


class HIVIDevice(BaseModel):
    """HIVI speaker device base class."""

    # Basic information
    speaker_device_id: str = ""  # Use device UDN as ID
    unique_id: str = ""
    friendly_name: str = ""
    model: str = ""
    manufacturer: str = ""
    ha_device_id: str = ""
    hardware: str = ""

    # Network information
    ip_addr: str = ""
    mac_address: str = ""
    hostname: str = ""

    # Device capabilities
    supports_dlna: bool = True
    supports_private_protocol: bool = True
    sync_group_status: SyncGroupStatus = SyncGroupStatus.STANDALONE

    # Status information
    connection_status: ConnectionStatus = ConnectionStatus.ONLINE
    last_seen: datetime = Field(default_factory=datetime.now)

    # Master-slave relationship
    master_speaker_device_id: str | None = None  # Master speaker ID
    slave_device_num: int = 0
    slave_device_list: list[SlaveDeviceInfo] = Field(default_factory=list)

    # DLNA information
    dlna_udn: str | None = None
    dlna_location: str | None = None

    # Private protocol information
    private_protocol_version: str | None = None
    private_port: int = 9527

    # Home Assistant integration
    entity_id: str | None = None
    config_entry_id: str | None = None

    # other info
    wifi_channel: str = "0"
    ssid: str | None = None
    auth_mode: str | None = None
    encryption_mode: str | None = None
    psk: str | None = None
    uuid: str | None = None

    def model_post_init(self, __context, /) -> None:
        """Auto-generate unique_id from mac_address if not provided."""
        if not self.unique_id:
            self.unique_id = f"hivi_{self.mac_address.replace(':', '')}"

    @property
    def is_available_for_media(self) -> bool:
        """Whether available as media player (non-slave speaker)."""
        return (
            self.sync_group_status != SyncGroupStatus.SLAVE
            and self.connection_status == ConnectionStatus.ONLINE
        )

    @property
    def can_be_master(self) -> bool:
        """Whether can be set as master speaker."""
        return (
            self.sync_group_status
            in {SyncGroupStatus.MASTER, SyncGroupStatus.STANDALONE}
            and self.connection_status == ConnectionStatus.ONLINE
        )

    @property
    def can_be_slave(self) -> bool:
        """Whether can be set as slave speaker."""
        return (
            self.sync_group_status == SyncGroupStatus.STANDALONE
            and self.connection_status == ConnectionStatus.ONLINE
        )  # Speakers already set as master cannot be set as slave
