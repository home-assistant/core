"""Constants."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .device import BroadlinkDevice
    from .heartbeat import BroadlinkHeartbeat

DOMAIN = "broadlink"

DOMAINS_AND_TYPES = {
    Platform.CLIMATE: {"HYS"},
    Platform.INFRARED: {"RM4MINI", "RM4PRO", "RM5PLUS", "RMMINI", "RMMINIB", "RMPRO"},
    Platform.LIGHT: {"LB1", "LB2"},
    Platform.RADIO_FREQUENCY: {"RM4PRO", "RMPRO"},
    Platform.REMOTE: {"RM4MINI", "RM4PRO", "RM5PLUS", "RMMINI", "RMMINIB", "RMPRO"},
    Platform.SELECT: {"HYS"},
    Platform.SENSOR: {
        "A1",
        "A2",
        "MP1S",
        "RM4MINI",
        "RM4PRO",
        "RMPRO",
        "SP2S",
        "SP3S",
        "SP4",
        "SP4B",
    },
    Platform.SWITCH: {
        "BG1",
        "MP1",
        "MP1S",
        "RM4MINI",
        "RM4PRO",
        "RM5PLUS",
        "RMMINI",
        "RMMINIB",
        "RMPRO",
        "SP1",
        "SP2",
        "SP2S",
        "SP3",
        "SP3S",
        "SP4",
        "SP4B",
    },
    Platform.TIME: {"HYS"},
}
DEVICE_TYPES = set.union(*DOMAINS_AND_TYPES.values())

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5


@dataclass
class BroadlinkData:
    """Class for sharing data within the Broadlink integration."""

    devices: dict[str, BroadlinkDevice] = field(default_factory=dict)
    platforms: dict = field(default_factory=dict)
    heartbeat: BroadlinkHeartbeat | None = None


BROADLINK_DATA: HassKey[BroadlinkData] = HassKey(DOMAIN)
