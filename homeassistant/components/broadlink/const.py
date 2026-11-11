"""Constants."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Final

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .device import BroadlinkDevice
    from .heartbeat import BroadlinkHeartbeat

DOMAIN = "broadlink"

CONF_ENTRY_KIND: Final = "entry_kind"
ENTRY_KIND_CLASSIC: Final = "classic"
ENTRY_KIND_MAGIC_FAMILY: Final = "magic_family"

CONF_FAMILY_ID: Final = "family_id"
CONF_FAMILY_NAME: Final = "family_name"
CONF_FAMILY_PID: Final = "family_pid"
CONF_FAMILY_TOKEN: Final = "family_token"
CONF_BLETOKEN: Final = "bletoken"
CONF_DEVICES: Final = "devices"
CONF_GATEWAYS: Final = "gateways"
CONF_GROUPS: Final = "groups"
CONF_ROOMS: Final = "rooms"
CONF_SCENES: Final = "scenes"
CONF_VIRTUAL_SUBTOKENS: Final = "virtual_subtokens"

IMPORT_PATH: Final = "/industry/v1/familyinfo/import"
IMPORT_TIMEOUT: Final = 180
UPDATE_INTERVAL: Final = timedelta(seconds=60)

MAGIC_PLATFORMS: Final = [
    Platform.CLIMATE,
    Platform.LIGHT,
    Platform.SWITCH,
]


def is_magic_entry(entry) -> bool:
    """Return whether a config entry represents a Magic Home family."""
    return entry.data.get(CONF_ENTRY_KIND) == ENTRY_KIND_MAGIC_FAMILY


def magic_family_identifier(family_id: str) -> str:
    """Return a namespaced Magic family device identifier."""
    return f"magic:family:{family_id}"


def magic_gateway_identifier(mac: str) -> str:
    """Return a namespaced Magic gateway device identifier."""
    return f"magic:gw:{mac}"


def magic_device_identifier(stable_id: str) -> str:
    """Return a namespaced Magic child device identifier."""
    return f"magic:dev:{stable_id}"


def magic_rm_device_identifier(stable_id: str) -> str:
    """Return a namespaced Magic RM child device identifier."""
    return f"magic:rm:{stable_id}"


DOMAINS_AND_TYPES = {
    Platform.BINARY_SENSOR: {"HYS"},
    Platform.CLIMATE: {"HYS"},
    Platform.INFRARED: {"RM4MINI", "RM4PRO", "RM5PLUS", "RMMINI", "RMMINIB", "RMPRO"},
    Platform.LIGHT: {"LB1", "LB2"},
    Platform.NUMBER: {"HYS"},
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
