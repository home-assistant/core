"""DoorBird Media Source Implementation."""
import logging
from typing import Optional, Tuple

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_IMAGE,
    MEDIA_TYPE_IMAGE,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.const import MEDIA_MIME_TYPES
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN, MANUFACTURER
from .util import get_all_doorstations, get_doorstation_by_slug

_LOGGER = logging.getLogger(__name__)
MIME_TYPE = "image/jpeg"

MIN_EVENT_ID = 1
MAX_EVENT_ID = 50

MEDIA_TYPE_DIRECTORY = "directory"

EVENT_IDS = range(MIN_EVENT_ID, MAX_EVENT_ID + 1)
SOURCES = ["doorbell", "motionsensor"]
SOURCE_NAMES = {"doorbell": "Doorbell", "motionsensor": "Motion Sensor"}


async def async_get_media_source(hass: HomeAssistant):
    """Set up DoorBird media source."""
    return DoorBirdSource(hass)


class DoorBirdSource(MediaSource):
    """Provide DoorBird camera recordings as media sources."""

    name: str = MANUFACTURER

    def __init__(self, hass: HomeAssistant):
        """Initialize DoorBird source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        camera_slug, source, event_id = async_parse_identifier(item)

        doorstation = get_doorstation_by_slug(self.hass, camera_slug)
        url = doorstation.device.history_image_url(event_id, source)

        return PlayMedia(url, MIME_TYPE)

    async def async_browse_media(
        self, item: MediaSourceItem, media_types: Tuple[str] = MEDIA_MIME_TYPES
    ) -> BrowseMediaSource:
        """Return media."""
        try:
            camera_slug, source, event_id = async_parse_identifier(item)
        except Unresolvable as err:
            raise BrowseError(str(err)) from err

        if camera_slug is None:
            media = BrowseMediaSource(
                domain=DOMAIN,
                identifier="",
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=MEDIA_TYPE_DIRECTORY,
                title=MANUFACTURER,
                can_play=False,
                can_expand=True,
                thumbnail=None,
            )
            media.children = []
            for doorstation in get_all_doorstations(self.hass):
                camera_slug = doorstation.slug
                camera_name = doorstation.name
                media.children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=camera_slug,
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_type=MEDIA_TYPE_DIRECTORY,
                        title=camera_name,
                        can_play=False,
                        can_expand=True,
                        thumbnail=None,
                    )
                )
            return media

        doorstation = get_doorstation_by_slug(self.hass, camera_slug)
        camera_name = doorstation.name

        if source is None:
            media = BrowseMediaSource(
                domain=DOMAIN,
                identifier=camera_slug,
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=MEDIA_TYPE_DIRECTORY,
                title=camera_name,
                can_play=False,
                can_expand=True,
                thumbnail=None,
            )
            media.children = []
            for available_source in SOURCES:
                media.children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"{camera_slug}/{available_source}",
                        media_class=MEDIA_CLASS_DIRECTORY,
                        media_content_type=MEDIA_TYPE_DIRECTORY,
                        title=SOURCE_NAMES[available_source],
                        can_play=False,
                        can_expand=True,
                        thumbnail=None,
                    )
                )
            return media

        media = BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{camera_slug}/{source}",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_DIRECTORY,
            title=SOURCE_NAMES[source],
            can_play=False,
            can_expand=True,
            thumbnail=None,
        )
        media.children = []
        for event_id in EVENT_IDS:
            media.children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{camera_slug}/{source}/{event_id}",
                    media_class=MEDIA_CLASS_IMAGE,
                    media_content_type=MEDIA_TYPE_IMAGE,
                    title=f"Event {event_id}",
                    can_play=True,
                    can_expand=False,
                    thumbnail=None,
                )
            )

        return media


@callback
def async_parse_identifier(
    item: MediaSourceItem,
) -> Tuple[str, str, Optional[int]]:
    """Parse identifier."""

    if not item.identifier:
        return None, None, None

    tup = item.identifier.lstrip("/").split("/")
    while len(tup) < 3:
        tup.append(None)

    tup[-1] = int(tup[-1]) if tup[-1] else None

    return tup
