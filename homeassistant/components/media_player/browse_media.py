"""Browse media features for media player."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any
from urllib.parse import quote

import yarl

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import (
    NoURLAvailableError,
    get_supervisor_network_url,
    get_url,
    is_hass_url,
)

from .const import CONTENT_AUTH_EXPIRY_TIME, MEDIA_CLASS_DIRECTORY

# Paths that we don't need to sign
PATHS_WITHOUT_AUTH = ("/api/tts_proxy/",)


@callback
def async_process_play_media_url(
    hass: HomeAssistant,
    media_content_id: str,
    *,
    allow_relative_url: bool = False,
    for_supervisor_network: bool = False,
) -> str:
    """Update a media URL with authentication if it points at Home Assistant."""
    parsed = yarl.URL(media_content_id)

    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return media_content_id

    if parsed.is_absolute():
        if not is_hass_url(hass, media_content_id):
            return media_content_id
    else:
        if media_content_id[0] != "/":
            raise ValueError("URL is relative, but does not start with a /")

    if parsed.query:
        logging.getLogger(__name__).debug(
            "Not signing path for content with query param"
        )
    elif parsed.path.startswith(PATHS_WITHOUT_AUTH):
        # We don't sign this path if it doesn't need auth. Although signing itself can't hurt,
        # some devices are unable to handle long URLs and the auth signature might push it over.
        pass
    else:
        signed_path = async_sign_path(
            hass,
            quote(parsed.path),
            timedelta(seconds=CONTENT_AUTH_EXPIRY_TIME),
        )
        media_content_id = str(parsed.join(yarl.URL(signed_path)))

    # convert relative URL to absolute URL
    if not parsed.is_absolute() and not allow_relative_url:
        base_url = None
        if for_supervisor_network:
            base_url = get_supervisor_network_url(hass)

        if not base_url:
            try:
                base_url = get_url(hass)
            except NoURLAvailableError as err:
                msg = "Unable to determine Home Assistant URL to send to device"
                if (
                    hass.config.api
                    and hass.config.api.use_ssl
                    and (not hass.config.external_url or not hass.config.internal_url)
                ):
                    msg += ". Configure internal and external URL in general settings."
                raise HomeAssistantError(msg) from err

        media_content_id = f"{base_url}{media_content_id}"

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
        if self.children_media_class is None and self.children:
            self.calculate_children_class()

        response: dict[str, Any] = {
            "title": self.title,
            "media_class": self.media_class,
            "media_content_type": self.media_content_type,
            "media_content_id": self.media_content_id,
            "children_media_class": self.children_media_class,
            "can_play": self.can_play,
            "can_expand": self.can_expand,
            "thumbnail": self.thumbnail,
        }

        if not parent:
            return response

        response["not_shown"] = self.not_shown

        if self.children:
            response["children"] = [
                child.as_dict(parent=False) for child in self.children
            ]
        else:
            response["children"] = []

        return response

    def calculate_children_class(self) -> None:
        """Count the children media classes and calculate the correct class."""
        self.children_media_class = MEDIA_CLASS_DIRECTORY
        assert self.children is not None
        proposed_class = self.children[0].media_class
        if all(child.media_class == proposed_class for child in self.children):
            self.children_media_class = proposed_class

    def __repr__(self) -> str:
        """Return representation of browse media."""
        return f"<BrowseMedia {self.title} ({self.media_class})>"
