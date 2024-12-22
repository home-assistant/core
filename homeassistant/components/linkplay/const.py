"""LinkPlay constants."""

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

from . import LinkPlaySharedData

DOMAIN = "linkplay"
SHARED_DATA = "shared_data"
SHARED_DATA_KEY: HassKey[LinkPlaySharedData] = HassKey(SHARED_DATA)
PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]
DATA_SESSION = "session"
