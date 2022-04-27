"""Text-to-speech media source."""
from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, Any

from yarl import URL

from homeassistant.components.media_player.const import MEDIA_CLASS_APP
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.network import get_url

from .const import DOMAIN

if TYPE_CHECKING:
    from . import SpeechManager


async def async_get_media_source(hass: HomeAssistant) -> TTSMediaSource:
    """Set up tts media source."""
    return TTSMediaSource(hass)


class TTSMediaSource(MediaSource):
    """Provide text-to-speech providers as media sources."""

    name: str = "Text to Speech"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize TTSMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        parsed = URL(item.identifier)
        if "message" not in parsed.query:
            raise Unresolvable("No message specified.")

        options = dict(parsed.query)
        kwargs: dict[str, Any] = {
            "engine": parsed.name,
            "message": options.pop("message"),
            "language": options.pop("language", None),
            "options": options,
        }
        if "cache" in options:
            kwargs["cache"] = options.pop("cache") == "true"

        manager: SpeechManager = self.hass.data[DOMAIN]

        try:
            url = await manager.async_get_url_path(**kwargs)
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err

        mime_type = mimetypes.guess_type(url)[0] or "audio/mpeg"

        if manager.base_url and manager.base_url != get_url(self.hass):
            url = f"{manager.base_url}{url}"

        return PlayMedia(url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            provider, _, params = item.identifier.partition("?")
            return self._provider_item(provider, params)

        # Root. List providers.
        manager: SpeechManager = self.hass.data[DOMAIN]
        children = [self._provider_item(provider) for provider in manager.providers]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_APP,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_APP,
            children=children,
        )

    @callback
    def _provider_item(
        self, provider_domain: str, params: str | None = None
    ) -> BrowseMediaSource:
        """Return provider item."""
        manager: SpeechManager = self.hass.data[DOMAIN]
        if (provider := manager.providers.get(provider_domain)) is None:
            raise BrowseError("Unknown provider")

        if params:
            params = f"?{params}"
        else:
            params = ""

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{provider_domain}{params}",
            media_class=MEDIA_CLASS_APP,
            media_content_type="provider",
            title=provider.name,
            thumbnail=f"https://brands.home-assistant.io/_/{provider_domain}/logo.png",
            can_play=False,
            can_expand=True,
        )
