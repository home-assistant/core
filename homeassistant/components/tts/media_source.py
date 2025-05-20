"""Text-to-speech media source."""

from __future__ import annotations

import json
from typing import TypedDict

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

from .const import DATA_COMPONENT, DATA_TTS_MANAGER, DOMAIN, MEDIA_SOURCE_STREAM_PATH
from .helper import get_engine_instance

URL_QUERY_TTS_OPTIONS = "tts_options"


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

    if (engine := async_resolve_engine(hass, engine)) is None:
        raise HomeAssistantError("Invalid TTS provider selected")

    engine_instance = get_engine_instance(hass, engine)
    # We raise above if the engine is not resolved, so engine_instance can't be None
    assert engine_instance is not None

    hass.data[DATA_TTS_MANAGER].process_options(engine_instance, language, options)
    params = {
        "message": message,
    }
    if cache is not None:
        params["cache"] = "true" if cache else "false"
    if language is not None:
        params["language"] = language
    params[URL_QUERY_TTS_OPTIONS] = json.dumps(options, separators=(",", ":"))

    return ms_generate_media_source_id(
        DOMAIN,
        str(URL.build(path=engine, query=params)),
    )


class MediaSourceOptions(TypedDict):
    """Media source options."""

    engine: str
    language: str | None
    options: dict | None
    use_file_cache: bool | None


class ParsedMediaSourceId(TypedDict):
    """Parsed media source ID."""

    options: MediaSourceOptions
    message: str


class ParsedMediaSourceStreamId(TypedDict):
    """Parsed media source ID for a stream."""

    stream: str


@callback
def parse_media_source_id(
    media_source_id: str,
) -> ParsedMediaSourceId | ParsedMediaSourceStreamId:
    """Turn a media source ID into options."""
    parsed = URL(media_source_id)

    if parsed.path.startswith(f"{MEDIA_SOURCE_STREAM_PATH}/"):
        return {"stream": parsed.path[len(MEDIA_SOURCE_STREAM_PATH) + 1 :]}

    if URL_QUERY_TTS_OPTIONS in parsed.query:
        try:
            options = json.loads(parsed.query[URL_QUERY_TTS_OPTIONS])
        except json.JSONDecodeError as err:
            raise Unresolvable(f"Invalid TTS options: {err.msg}") from err
    else:
        options = {
            k: v
            for k, v in parsed.query.items()
            if k not in ("message", "language", "cache")
        }
    if "message" not in parsed.query:
        raise Unresolvable("No message specified.")
    kwargs: MediaSourceOptions = {
        "engine": parsed.name,
        "language": parsed.query.get("language"),
        "options": options,
        "use_file_cache": None,
    }
    if "cache" in parsed.query:
        kwargs["use_file_cache"] = parsed.query["cache"] == "true"

    return {"message": parsed.query["message"], "options": kwargs}


class TTSMediaSource(MediaSource):
    """Provide text-to-speech providers as media sources."""

    name: str = "Text-to-speech"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize TTSMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve media to a url."""
        manager = self.hass.data[DATA_TTS_MANAGER]
        try:
            parsed = parse_media_source_id(item.identifier)
            if "stream" in parsed:
                stream = manager.async_get_result_stream(
                    parsed["stream"],  # type: ignore[typeddict-item]
                )
            else:
                stream = manager.async_create_result_stream(**parsed["options"])
                stream.async_set_message(parsed["message"])
        except Unresolvable:
            raise
        except HomeAssistantError as err:
            raise Unresolvable(str(err)) from err

        if stream is None:
            raise Unresolvable("Stream not found")

        return PlayMedia(stream.url, stream.content_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        if item.identifier:
            engine, _, params = item.identifier.partition("?")
            return self._engine_item(engine, params)

        # Root. List providers.
        children = sorted(
            [
                self._engine_item(engine_id)
                for engine_id, provider in self.hass.data[
                    DATA_TTS_MANAGER
                ].providers.items()
                if not provider.has_entity
            ]
            + [
                self._engine_item(entity.entity_id)
                for entity in self.hass.data[DATA_COMPONENT].entities
            ],
            key=lambda x: x.title,
        )
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
            engine_domain = engine_instance.platform.platform_name
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
