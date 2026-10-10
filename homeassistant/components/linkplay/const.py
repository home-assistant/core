"""LinkPlay constants."""

from dataclasses import dataclass

from linkplay.controller import LinkPlayController

from homeassistant.const import Platform
from homeassistant.util.hass_dict import HassKey


@dataclass
class LinkPlaySharedData:
    """Shared data for LinkPlay."""

    controller: LinkPlayController
    entity_to_bridge: dict[str, str]


DOMAIN = "linkplay"
ENTITY_ID_CHANGED_SIGNAL = f"{DOMAIN}_entity_id_changed"
SHARED_DATA = "shared_data"
SHARED_DATA_KEY: HassKey[LinkPlaySharedData] = HassKey(SHARED_DATA)
PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.SELECT]
DATA_SESSION = "session"
