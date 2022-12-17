"""Helper classes for Google Assistant SDK integration."""
from __future__ import annotations

import aiohttp
from gassist_text import TextAssistant
from google.oauth2.credentials import Credentials

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import CONF_LANGUAGE_CODE, DOMAIN, SUPPORTED_LANGUAGE_CODES

DEFAULT_LANGUAGE_CODES = {
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "pt": "pt-BR",
}


async def async_send_text_commands(commands: list[str], hass: HomeAssistant) -> None:
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
    with TextAssistant(credentials, language_code) as assistant:
        for command in commands:
            assistant.assist(command)


def default_language_code(hass: HomeAssistant):
    """Get default language code based on Home Assistant config."""
    language_code = f"{hass.config.language}-{hass.config.country}"
    if language_code in SUPPORTED_LANGUAGE_CODES:
        return language_code
    return DEFAULT_LANGUAGE_CODES.get(hass.config.language, "en-US")
