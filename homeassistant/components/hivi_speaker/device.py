from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import asyncio
from datetime import datetime
from pydantic import BaseModel


class SyncGroupStatus(Enum):
    """Device type enumeration"""

    UNKNOWN = "unknown"
    MASTER = "master"  # Master speaker
    SLAVE = "slave"  # Slave speaker
    STANDALONE = "standalone"  # Standalone speaker (can be master or slave)


class ConnectionStatus(Enum):
    """Device status"""

    ONLINE = "online"
    OFFLINE = "offline"
    UNAVAILABLE = "unavailable"


class SlaveDeviceInfo(BaseModel):
    """Slave speaker information class"""

    friendly_name: str
    ssid: str
    mask: Optional[int]
    volume: int
    mute: bool
    channel: int
    battery: Optional[int]
    ip_addr: str
    version: str
    uuid: str


class HIVIDevice(BaseModel):
    """HIVI speaker device base class"""

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
    last_seen: datetime

    # Master-slave relationship
    master_speaker_device_id: Optional[str] = None  # Master speaker ID
    slave_device_num: int = 0
    slave_device_list: list[SlaveDeviceInfo]

    # DLNA information
    dlna_udn: Optional[str] = None
    dlna_location: Optional[str] = None

    # Private protocol information
    private_protocol_version: Optional[str] = None
    private_port: int = 9527

    # Home Assistant integration
    entity_id: Optional[str] = None
    config_entry_id: Optional[str] = None
    # switch_entities: dict = field(default_factory=dict)

    # other info
    wifi_channel: str = "0"
    ssid: Optional[str] = None
    auth_mode: Optional[str] = None
    encryption_mode: Optional[str] = None
    psk: Optional[str] = None
    uuid: Optional[str] = None

    def __post_init__(self):
        """Post-initialization processing"""
        if not self.unique_id:
            self.unique_id = f"hivi_{self.mac_address.replace(':', '')}"

    @property
    def is_available_for_media(self) -> bool:
        """Whether available as media player (non-slave speaker)"""
        return (
            self.sync_group_status != SyncGroupStatus.SLAVE
            and self.connection_status == ConnectionStatus.ONLINE
        )

    @property
    def can_be_master(self) -> bool:
        """Whether can be set as master speaker"""
        return (
            self.sync_group_status
            in [SyncGroupStatus.MASTER, SyncGroupStatus.STANDALONE]
            and self.connection_status == ConnectionStatus.ONLINE
        )

    @property
    def can_be_slave(self) -> bool:
        """Whether can be set as slave speaker"""
        return (
            self.sync_group_status == SyncGroupStatus.STANDALONE
            and self.connection_status == ConnectionStatus.ONLINE
        )  # Speakers already set as master cannot be set as slave
