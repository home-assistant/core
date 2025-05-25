"""LinkPlay constants."""

from dataclasses import dataclass

from linkplay.consts import AudioOutputHwMode
from linkplay.controller import LinkPlayController

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey


@dataclass
class LinkPlaySharedData:
    """Shared data for LinkPlay."""

    controller: LinkPlayController
    entity_to_bridge: dict[str, str]


DOMAIN = "linkplay"
SHARED_DATA = "shared_data"
SHARED_DATA_KEY: HassKey[LinkPlaySharedData] = HassKey(SHARED_DATA)
PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.SELECT]
DATA_SESSION = "session"

AUDIO_OUTPUT_HW_MODE_MAP: dict[AudioOutputHwMode, str] = {
    AudioOutputHwMode.OPTICAL: "Optical",
    AudioOutputHwMode.LINE_OUT: "Line Out",
    AudioOutputHwMode.COAXIAL: "Coaxial",
    AudioOutputHwMode.HEADPHONES: "Headphones",
}

AUDIO_OUTPUT_HW_MODE_MAP_INV: dict[str, AudioOutputHwMode] = {
    v: k for k, v in AUDIO_OUTPUT_HW_MODE_MAP.items()
}
