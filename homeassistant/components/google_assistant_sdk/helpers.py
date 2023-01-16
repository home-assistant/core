"""Helper classes for Google Assistant SDK integration."""
from __future__ import annotations

from http import HTTPStatus
import logging
import uuid

import aiohttp
from aiohttp import web
from gassist_text import TextAssistant
from google.oauth2.credentials import Credentials

from homeassistant.components.http import HomeAssistantView
from homeassistant.components.media_player import (
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as DOMAIN_MP,
    SERVICE_PLAY_MEDIA,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import (
    CONF_LANGUAGE_CODE,
    DATA_AUDIO_VIEW,
    DATA_SESSION,
    DOMAIN,
    SUPPORTED_LANGUAGE_CODES,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_LANGUAGE_CODES = {
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "pt": "pt-BR",
}


async def async_send_text_commands(
    hass: HomeAssistant, commands: list[str], media_players: list[str] | None = None
) -> None:
    """Send text commands to Google Assistant Service."""
    # There can only be 1 entry (config_flow has single_instance_allowed)
    entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    session: OAuth2Session = hass.data[DOMAIN][entry.entry_id][DATA_SESSION]
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            entry.async_start_reauth(hass)
        raise err

    credentials = Credentials(session.token[CONF_ACCESS_TOKEN])
    language_code = entry.options.get(CONF_LANGUAGE_CODE, default_language_code(hass))
    with TextAssistant(
        credentials, language_code, audio_out=bool(media_players)
    ) as assistant:
        for command in commands:
            resp = assistant.assist(command)
            text_response = resp[0]
            _LOGGER.debug("command: %s\nresponse: %s", command, text_response)
            audio_response = resp[2]
            if media_players and audio_response:
                audio_view: GoogleAssistantSDKAudioView = hass.data[DOMAIN][
                    entry.entry_id
                ][DATA_AUDIO_VIEW]
                await hass.services.async_call(
                    DOMAIN_MP,
                    SERVICE_PLAY_MEDIA,
                    {
                        ATTR_ENTITY_ID: media_players,
                        ATTR_MEDIA_CONTENT_ID: audio_view.memcache_store_and_get_url(
                            audio_response
                        ),
                        ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                        ATTR_MEDIA_ANNOUNCE: True,
                    },
                    blocking=True,
                )


def default_language_code(hass: HomeAssistant):
    """Get default language code based on Home Assistant config."""
    language_code = f"{hass.config.language}-{hass.config.country}"
    if language_code in SUPPORTED_LANGUAGE_CODES:
        return language_code
    return DEFAULT_LANGUAGE_CODES.get(hass.config.language, "en-US")


class GoogleAssistantSDKAudioView(HomeAssistantView):
    """Google Assistant SDK view to serve audio responses."""

    requires_auth = False
    url = "/api/google_assistant_sdk/audio/{filename}"
    name = "api:google_assistant_sdk:audio"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize GoogleAssistantSDKView."""
        self.hass: HomeAssistant = hass
        self.mem_cache: dict[str, bytes] = {}

    def memcache_store_and_get_url(self, audio: bytes) -> str:
        """Write audio to memcache and return URL to serve it."""
        filename: str = uuid.uuid1().hex
        self.mem_cache[filename] = audio

        def async_remove_from_mem() -> None:
            """Cleanup memcache."""
            self.mem_cache.pop(filename, None)

        # Remove the entry from memcache 5 minutes later
        self.hass.loop.call_later(5 * 60, async_remove_from_mem)

        return self.url.format(filename=filename)

    async def get(self, request: web.Request, filename: str) -> web.Response:
        """Start a get request."""
        audio = self.mem_cache.get(filename)
        if not audio:
            return web.Response(status=HTTPStatus.NOT_FOUND)
        return web.Response(body=audio, content_type="audio/mpeg")
