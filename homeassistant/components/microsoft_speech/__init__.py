"""The Microsoft Speech integration."""

from __future__ import annotations

import azure.cognitiveservices.speech as speechsdk

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LANGUAGE, CONF_REGION, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)

from .const import DATA_SPEECH_CONFIG

PLATFORMS: list[Platform] = [Platform.STT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Microsoft Speech from a config entry."""
    speech_config = speechsdk.SpeechConfig(
        subscription=entry.data[CONF_API_KEY],
        region=entry.data[CONF_REGION],
        speech_recognition_language=entry.data[CONF_LANGUAGE],
    )

    synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config)
    voices_future = await hass.async_add_executor_job(synthesizer.get_voices_async)
    voices_result = await hass.async_add_executor_job(voices_future.get)

    if voices_result.reason == speechsdk.ResultReason.VoicesListRetrieved:
        entry.runtime_data = {}
        entry.runtime_data[DATA_SPEECH_CONFIG] = speech_config
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    if voices_result.reason == speechsdk.ResultReason.Canceled:
        if hasattr(voices_result, "error_details"):
            if "Authentication error" in voices_result.error_details:
                raise ConfigEntryAuthFailed("Invalid API key or region")
            if "HTTPAPI_OPEN_REQUEST_FAILED" in voices_result.error_details:
                raise ConfigEntryNotReady(
                    "Timed out while connecting to Microsoft Azure"
                )
        raise ConfigEntryError("Unknown error while connecting to Microsoft Azure")

    return False


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
