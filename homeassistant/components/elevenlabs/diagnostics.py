"""Diagnostics support for ElevenLabs."""

from collections import Counter
from typing import Any

from homeassistant.core import HomeAssistant

from . import ElevenLabsConfigEntry
from .const import CONF_STT_AUTO_LANGUAGE, CONF_VOICE
from .tts import to_voice_settings

# Voices in this category are the public voices offered by ElevenLabs.
PUBLIC_VOICE_CATEGORY = "premade"


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ElevenLabsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    voice_settings = to_voice_settings(entry.options)

    selected_voice_id = entry.options[CONF_VOICE]
    selected_voice = next(
        (voice for voice in data.voices if voice.voice_id == selected_voice_id), None
    )
    selected_category = selected_voice.category if selected_voice else None

    # The API key is left out. Voice names and the IDs of voices that are not
    # public are left out too, as cloned or generated voices can be personal.
    return {
        "config_entry": {
            CONF_STT_AUTO_LANGUAGE: entry.options.get(CONF_STT_AUTO_LANGUAGE),
            "voice_settings": {
                "stability": voice_settings.stability,
                "similarity_boost": voice_settings.similarity_boost,
                "style": voice_settings.style,
                "use_speaker_boost": voice_settings.use_speaker_boost,
            },
        },
        "tts_model": {
            "model_id": data.model.model_id,
            "can_do_text_to_speech": data.model.can_do_text_to_speech,
            "languages": len(data.model.languages or []),
        },
        "stt_model": data.stt_model,
        "voices": {
            "count": len(data.voices),
            "categories": dict(
                Counter(str(voice.category or "unknown") for voice in data.voices)
            ),
            "selected_voice_found": selected_voice is not None,
            "selected_voice_category": (
                str(selected_category) if selected_category else None
            ),
            "selected_voice_id": (
                selected_voice_id
                if selected_category == PUBLIC_VOICE_CATEGORY
                else None
            ),
        },
    }
