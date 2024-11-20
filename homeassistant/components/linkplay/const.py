"""LinkPlay constants."""

from linkplay.controller import LinkPlayController

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey

DOMAIN = "linkplay"
CONTROLLER = "controller"
CONTROLLER_KEY: HassKey[LinkPlayController] = HassKey(CONTROLLER)
PLATFORMS = [Platform.MEDIA_PLAYER]
DATA_SESSION = "session"
