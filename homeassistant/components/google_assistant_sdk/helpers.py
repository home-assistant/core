"""Helper classes for Google Assistant SDK integration."""
from __future__ import annotations

import logging

import aiohttp
from gassist_text import TextAssistant
from google.oauth2.credentials import Credentials

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import CONF_LANGUAGE_CODE, DOMAIN, SUPPORTED_LANGUAGE_CODES

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


async def _async_send_text_commands(
    hass: HomeAssistant, commands: list[str], audio_out: bool
) -> bytes | None:
    """Send text commands to Google Assistant Service."""
    # There can only be 1 entry (config_flow has single_instance_allowed)
    entry: ConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]

    session: OAuth2Session = hass.data[DOMAIN].get(entry.entry_id)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            entry.async_start_reauth(hass)
        raise err

    credentials = Credentials(session.token[CONF_ACCESS_TOKEN])
    language_code = entry.options.get(CONF_LANGUAGE_CODE, default_language_code(hass))
    with TextAssistant(credentials, language_code, audio_out=audio_out) as assistant:
        for command in commands:
            resp = assistant.assist(command)
            text_response = resp[0]
            _LOGGER.debug("command: %s\nresponse: %s", command, text_response)
            audio_response = resp[2]
            if audio_out:
                assert len(commands) == 1
                return audio_response
    return None


async def async_send_text_commands(hass: HomeAssistant, commands: list[str]) -> None:
    """Send text commands to Google Assistant Service."""
    await _async_send_text_commands(hass, commands, False)


async def async_send_text_command_with_audio(
    hass: HomeAssistant, command: str
) -> bytes | None:
    """Send a text command to Google Assistant Service and return the audio response."""
    return await _async_send_text_commands(hass, [command], True)


def default_language_code(hass: HomeAssistant):
    """Get default language code based on Home Assistant config."""
    language_code = f"{hass.config.language}-{hass.config.country}"
    if language_code in SUPPORTED_LANGUAGE_CODES:
        return language_code
    return DEFAULT_LANGUAGE_CODES.get(hass.config.language, "en-US")
