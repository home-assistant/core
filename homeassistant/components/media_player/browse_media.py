"""Browse media features for media player."""
from __future__ import annotations

from datetime import timedelta
import logging
from urllib.parse import quote

import yarl

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.network import get_url, is_hass_url

from .const import CONTENT_AUTH_EXPIRY_TIME, MEDIA_CLASS_DIRECTORY


@callback
def async_process_play_media_url(hass: HomeAssistant, media_content_id: str) -> str:
    """Update a media URL with authentication if it points at Home Assistant."""
    if media_content_id[0] != "/" and not is_hass_url(hass, media_content_id):
        return media_content_id

    parsed = yarl.URL(media_content_id)

    if parsed.query:
        logging.getLogger(__name__).debug(
            "Not signing path for content with query param"
        )
    else:
        signed_path = async_sign_path(
            hass,
            quote(parsed.path),
            timedelta(seconds=CONTENT_AUTH_EXPIRY_TIME),
        )
        media_content_id = str(parsed.join(yarl.URL(signed_path)))

    # prepend external URL
    if media_content_id[0] == "/":
        media_content_id = f"{get_url(hass)}{media_content_id}"

    return media_content_id


class BrowseMedia:
    """Represent a browsable media file."""

    def __init__(
        self,
        *,
        media_class: str,
        media_content_id: str,
        media_content_type: str,
        title: str,
        can_play: bool,
        can_expand: bool,
        children: list[BrowseMedia] | None = None,
        children_media_class: str | None = None,
        thumbnail: str | None = None,
        not_shown: int = 0,
    ) -> None:
        """Initialize browse media item."""
        self.media_class = media_class
        self.media_content_id = media_content_id
        self.media_content_type = media_content_type
        self.title = title
        self.can_play = can_play
        self.can_expand = can_expand
        self.children = children
        self.children_media_class = children_media_class
        self.thumbnail = thumbnail
        self.not_shown = not_shown

    def as_dict(self, *, parent: bool = True) -> dict:
        """Convert Media class to browse media dictionary."""
        response = {
            "title": self.title,
            "media_class": self.media_class,
            "media_content_type": self.media_content_type,
            "media_content_id": self.media_content_id,
            "can_play": self.can_play,
            "can_expand": self.can_expand,
            "thumbnail": self.thumbnail,
        }

        if not parent:
            return response

        if self.children_media_class is None:
            self.calculate_children_class()

        response["not_shown"] = self.not_shown
        response["children_media_class"] = self.children_media_class

        if self.children:
            response["children"] = [
                child.as_dict(parent=False) for child in self.children
            ]
        else:
            response["children"] = []

        return response

    def calculate_children_class(self) -> None:
        """Count the children media classes and calculate the correct class."""
        if self.children is None or len(self.children) == 0:
            return

        self.children_media_class = MEDIA_CLASS_DIRECTORY

        proposed_class = self.children[0].media_class
        if all(child.media_class == proposed_class for child in self.children):
            self.children_media_class = proposed_class

    def __repr__(self) -> str:
        """Return representation of browse media."""
        return f"<BrowseMedia {self.title} ({self.media_class})>"
