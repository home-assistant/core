"""Text-to-speech media source."""

from __future__ import annotations

import mimetypes
from typing import TYPE_CHECKING, TypedDict

from yarl import URL

from homeassistant.components.media_player import BrowseError, MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
    generate_media_source_id as ms_generate_media_source_id,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent

from .const import DATA_TTS_MANAGER, DOMAIN
from .helper import get_engine_instance

if TYPE_CHECKING:
    from . import SpeechManager, TextToSpeechEntity


async def async_get_media_source(hass: HomeAssistant) -> TTSMediaSource:
    """Set up tts media source."""
    return TTSMediaSource(hass)


@callback
def generate_media_source_id(
    hass: HomeAssistant,
    message: str,
    engine: str | None = None,
    language: str | None = None,
    options: dict | None = None,
    cache: bool | None = None,
) -> str:
    """Generate a media source ID for text-to-speech."""
    from . import async_resolve_engine  # pylint: disable=import-outside-toplevel

    manager: SpeechManager = hass.data[DATA_TTS_MANAGER]

    if (engine := async_resolve_engine(hass, engine)) is None:
        raise HomeAssistantError("Invalid TTS provider selected")

    engine_instance = get_engine_instance(hass, engine)
    # We raise above if the engine is not resolved, so engine_instance can't be None
    assert engine_instance is not None

    manager.process_options(engine_instance, language, options)
    params = {
        "message": message,
    }
    if cache is not None:
        params["cache"] = "true" if cache else "false"
    if language is not None:
        params["language"] = language
    if options is not None:
        params.update(options)

    return ms_generate_media_source_id(
        DOMAIN,
        str(URL.build(path=engine, query=params)),
    )


class MediaSourceOptions(TypedDict):
    """Media source options."""

    engine: str
    message: str
    language: str | None
    options: dict | None
    cache: bool | None


@callback
def media_source_id_to_kwargs(media_source_id: str) -> MediaSourceOptions:
    """Turn a media source ID into options."""
    parsed = URL(media_source_id)
    if "message" not in parsed.query:
        raise Unresolvable("No message specified.")

    options = dict(parsed.query)
    kwargs: MediaSourceOptions = {
        "engine": parsed.name,
        "message": options.pop("message"),
        "language": options.pop("language", None),
        "options": options,
        "cache": None,
    }
    if "cache" in options:
        kwargs["cache"] = options.pop("cache") == "true"

    return kwargs


class TTSMediaSource(MediaSource):
    """Provide text-to-speech providers as media sources."""

    name: str = "Text-to-speech"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize TTSMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        manager: SpeechManager = self.hass.data[DATA_TTS_MANAGER]

        try:
            url = await manager.async_get_url_path(
                **media_source_id_to_kwargs(item.identifier)
            )
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err

        mime_type = mimetypes.guess_type(url)[0] or "audio/mpeg"

        return PlayMedia(url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            engine, _, params = item.identifier.partition("?")
            return self._engine_item(engine, params)

        # Root. List providers.
        manager: SpeechManager = self.hass.data[DATA_TTS_MANAGER]
        component: EntityComponent[TextToSpeechEntity] = self.hass.data[DOMAIN]
        children = [self._engine_item(engine) for engine in manager.providers] + [
            self._engine_item(entity.entity_id) for entity in component.entities
        ]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.APP,
            media_content_type="",
            title=self.name,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.APP,
            children=children,
        )

    @callback
    def _engine_item(self, engine: str, params: str | None = None) -> BrowseMediaSource:
        """Return provider item."""
        from . import TextToSpeechEntity  # pylint: disable=import-outside-toplevel

        if (engine_instance := get_engine_instance(self.hass, engine)) is None:
            raise BrowseError("Unknown provider")

        if isinstance(engine_instance, TextToSpeechEntity):
            engine_domain = engine_instance.platform.domain
        else:
            engine_domain = engine

        if params:
            params = f"?{params}"
        else:
            params = ""

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{engine}{params}",
            media_class=MediaClass.APP,
            media_content_type="provider",
            title=engine_instance.name,
            thumbnail=f"https://brands.home-assistant.io/_/{engine_domain}/logo.png",
            can_play=False,
            can_expand=True,
        )
