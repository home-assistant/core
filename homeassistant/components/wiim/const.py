"""Constants for the WiiM integration."""

import logging
from typing import TYPE_CHECKING, Final

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from wiim import WiimDevice

    from .models import WiimData

type WiimConfigEntry = ConfigEntry[WiimDevice]

DOMAIN: Final = "wiim"
LOGGER = logging.getLogger(__package__)
DATA_WIIM: HassKey[WiimData] = HassKey(DOMAIN)

PLATFORMS: Final[list[Platform]] = [
    Platform.MEDIA_PLAYER,
]

UPNP_PORT = 49152

ZEROCONF_TYPE_LINKPLAY: Final = "_linkplay._tcp.local."
