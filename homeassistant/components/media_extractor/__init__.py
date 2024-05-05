"""Decorator service for the media_player.play_media service."""

from collections.abc import Callable
import logging
from pathlib import Path
from typing import Any, cast

import voluptuous as vol
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError, ExtractorError

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from .const import (
    ATTR_FORMAT_QUERY,
    ATTR_URL,
    DEFAULT_STREAM_QUERY,
    DOMAIN,
    SERVICE_EXTRACT_MEDIA_URL,
)

_LOGGER = logging.getLogger(__name__)

CONF_CUSTOMIZE_ENTITIES = "customize"
CONF_DEFAULT_STREAM_QUERY = "default_query"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEFAULT_STREAM_QUERY): cv.string,
                vol.Optional(CONF_CUSTOMIZE_ENTITIES): vol.Schema(
                    {cv.entity_id: vol.Schema({cv.string: cv.string})}
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Media Extractor from a config entry."""

    return True


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the media extractor service."""

    if DOMAIN in config:
        async_create_issue(
            hass,
            HOMEASSISTANT_DOMAIN,
            f"deprecated_yaml_{DOMAIN}",
            breaks_in_ha_version="2024.11.0",
            is_fixable=False,
            issue_domain=DOMAIN,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Media extractor",
            },
        )

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
            )
        )

    async def extract_media_url(call: ServiceCall) -> ServiceResponse:
        """Extract media url."""

        def extract_info() -> dict[str, Any]:
            youtube_dl = YoutubeDL(
                {
                    "quiet": True,
                    "logger": _LOGGER,
                    "format": call.data[ATTR_FORMAT_QUERY],
                }
            )
            return cast(
                dict[str, Any],
                youtube_dl.extract_info(
                    call.data[ATTR_URL], download=False, process=False
                ),
            )

        result = await hass.async_add_executor_job(extract_info)
        if "entries" in result:
            _LOGGER.warning("Playlists are not supported, looking for the first video")
            entries = list(result["entries"])
            if entries:
                selected_media = entries[0]
            else:
                raise HomeAssistantError("Playlist is empty")
        else:
            selected_media = result
        if "formats" in selected_media:
            if selected_media["extractor"] == "youtube":
                url = get_best_stream_youtube(selected_media["formats"])
            else:
                url = get_best_stream(selected_media["formats"])
        else:
            url = cast(str, selected_media["url"])
        return {"url": url}

    def play_media(call: ServiceCall) -> None:
        """Get stream URL and send it to the play_media service."""
        MediaExtractor(hass, config.get(DOMAIN, {}), call.data).extract_and_send()

    default_format_query = config.get(DOMAIN, {}).get(
        CONF_DEFAULT_STREAM_QUERY, DEFAULT_STREAM_QUERY
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_EXTRACT_MEDIA_URL,
        extract_media_url,
        schema=vol.Schema(
            {
                vol.Required(ATTR_URL): cv.string,
                vol.Optional(
                    ATTR_FORMAT_QUERY, default=default_format_query
                ): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_PLAY_MEDIA,
        play_media,
        schema=cv.make_entity_service_schema(MEDIA_PLAYER_PLAY_MEDIA_SCHEMA),
    )

    return True


class MEDownloadException(Exception):
    """Media extractor download exception."""


class MEQueryException(Exception):
    """Media extractor query exception."""


class MediaExtractor:
    """Class which encapsulates all extraction logic."""

    def __init__(
        self,
        hass: HomeAssistant,
        component_config: dict[str, Any],
        call_data: dict[str, Any],
    ) -> None:
        """Initialize media extractor."""
        self.hass = hass
        self.config = component_config
        self.call_data = call_data

    def get_media_url(self) -> str:
        """Return media content url."""
        return cast(str, self.call_data[ATTR_MEDIA_CONTENT_ID])

    def get_entities(self) -> list[str]:
        """Return list of entities."""
        return self.call_data.get(ATTR_ENTITY_ID, [])  # type: ignore[no-any-return]

    def extract_and_send(self) -> None:
        """Extract exact stream format for each entity_id and play it."""
        try:
            stream_selector = self.get_stream_selector()
        except MEDownloadException:
            _LOGGER.error(
                "Could not retrieve data for the URL: %s", self.get_media_url()
            )
        else:
            if not (entities := self.get_entities()):
                self.call_media_player_service(stream_selector, None)

            for entity_id in entities:
                self.call_media_player_service(stream_selector, entity_id)

    def get_stream_selector(self) -> Callable[[str], str]:
        """Return format selector for the media URL."""
        cookies_file = Path(
            self.hass.config.config_dir, "media_extractor", "cookies.txt"
        )
        ydl_params = {"quiet": True, "logger": _LOGGER}
        if cookies_file.exists():
            ydl_params["cookiefile"] = str(cookies_file)
            _LOGGER.debug(
                "Media extractor loaded cookies file from: %s", str(cookies_file)
            )
        else:
            _LOGGER.debug(
                "Media extractor didn't find cookies file at: %s", str(cookies_file)
            )
        ydl = YoutubeDL(ydl_params)

        try:
            all_media = ydl.extract_info(self.get_media_url(), process=False)
        except DownloadError as err:
            # This exception will be logged by youtube-dl itself
            raise MEDownloadException from err

        if "entries" in all_media:
            _LOGGER.warning("Playlists are not supported, looking for the first video")
            entries = list(all_media["entries"])
            if entries:
                selected_media = entries[0]
            else:
                _LOGGER.error("Playlist is empty")
                raise MEDownloadException
        else:
            selected_media = all_media

        def stream_selector(query: str) -> str:
            """Find stream URL that matches query."""
            try:
                ydl.params["format"] = query
                requested_stream = ydl.process_ie_result(selected_media, download=False)
            except (ExtractorError, DownloadError) as err:
                _LOGGER.error("Could not extract stream for the query: %s", query)
                raise MEQueryException from err

            if "formats" in requested_stream:
                if requested_stream["extractor"] == "youtube":
                    return get_best_stream_youtube(requested_stream["formats"])
                return get_best_stream(requested_stream["formats"])
            return cast(str, requested_stream["url"])

        return stream_selector

    def call_media_player_service(
        self, stream_selector: Callable[[str], str], entity_id: str | None
    ) -> None:
        """Call Media player play_media service."""
        stream_query = self.get_stream_query_for_entity(entity_id)

        try:
            stream_url = stream_selector(stream_query)
        except MEQueryException:
            _LOGGER.error("Wrong query format: %s", stream_query)
            return
        _LOGGER.debug("Selected the following stream: %s", stream_url)
        data = {k: v for k, v in self.call_data.items() if k != ATTR_ENTITY_ID}
        data[ATTR_MEDIA_CONTENT_ID] = stream_url

        if entity_id:
            data[ATTR_ENTITY_ID] = entity_id

        self.hass.create_task(
            self.hass.services.async_call(MEDIA_PLAYER_DOMAIN, SERVICE_PLAY_MEDIA, data)
        )

    def get_stream_query_for_entity(self, entity_id: str | None) -> str:
        """Get stream format query for entity."""
        default_stream_query: str = self.config.get(
            CONF_DEFAULT_STREAM_QUERY, DEFAULT_STREAM_QUERY
        )

        if entity_id:
            media_content_type = self.call_data.get(ATTR_MEDIA_CONTENT_TYPE)

            return str(
                self.config.get(CONF_CUSTOMIZE_ENTITIES, {})
                .get(entity_id, {})
                .get(media_content_type, default_stream_query)
            )

        return default_stream_query


def get_best_stream(formats: list[dict[str, Any]]) -> str:
    """Return the best quality stream.

    As per
    https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/common.py#L128.
    """

    return cast(str, formats[len(formats) - 1]["url"])


def get_best_stream_youtube(formats: list[dict[str, Any]]) -> str:
    """YouTube responses also include files with only video or audio.

    So we filter on files with both audio and video codec.
    """

    return get_best_stream(
        [
            stream_format
            for stream_format in formats
            if stream_format.get("acodec", "none") != "none"
            and stream_format.get("vcodec", "none") != "none"
        ]
    )
