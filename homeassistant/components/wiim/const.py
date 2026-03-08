"""Constants for the WiiM integration."""

from dataclasses import dataclass, field
import logging
from typing import Final

from wiim.controller import WiimController

from homeassistant.const import Platform

DOMAIN: Final = "wiim"
LOGGER = logging.getLogger(__package__)

PLATFORMS: Final[list[Platform]] = [
    Platform.MEDIA_PLAYER,
]

CONF_UDN = "udn"
CONF_UPNP_LOCATION = "upnp_location"
UPNP_PORT = 49152

ZEROCONF_TYPE_LINKPLAY: Final = "_linkplay._tcp.local."

DEFAULT_AVAILABILITY_POLLING_INTERVAL = 60


@dataclass
class WiimData:
    """Runtime data for the WiiM integration shared across platforms."""

    controller: WiimController
    entity_id_to_udn_map: dict[str, str] = field(default_factory=dict)
