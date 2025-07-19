# homeassistant/components/wiim/const.py
"""Constants for the WiiM integration."""

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Final

from wiim.controller import WiimController

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .media_player import WiimMediaPlayerEntity

DOMAIN: Final = "wiim"
SDK_LOGGER = logging.getLogger(__package__)

PLATFORMS: Final[list[Platform]] = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
]

CONF_UDN = "udn"
CONF_NAME = "name"
CONF_UPNP_LOCATION = "upnp_location"
CONF_DEVICES = "devices"

DEFAULT_DEVICE_NAME = "WiiM Player"

UPNP_ST_MEDIA_RENDERER: Final = "urn:schemas-upnp-org:device:MediaRenderer:1"
ZEROCONF_TYPE_LINKPLAY: Final = "_linkplay._tcp.local."

DEFAULT_AVAILABILITY_POLLING_INTERVAL = 60


@dataclass
class WiimData:
    """Runtime data for the WiiM integration shared across platforms."""

    controller: WiimController
    entity_id_to_udn_map: dict[str, str] = field(default_factory=dict)
    entities_by_entity_id: dict[str, "WiimMediaPlayerEntity"] = field(
        default_factory=dict
    )


WIIM_SHARED_DATA_KEY: HassKey[WiimData] = HassKey(DOMAIN)
