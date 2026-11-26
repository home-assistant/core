"""Text-to-speech support for LiteLLM."""

from typing import Any, override

from openai import (
    APIConnectionError,
    AuthenticationError,
    OpenAIError,
    PermissionDeniedError,
)

from homeassistant.components.tts import (
    TextToSpeechCommonOption,
    TextToSpeechEntity,
    TtsAudioType,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_TTS_VOICE, SUPPORTED_LANGUAGES
from .coordinator import LiteLLMConfigEntry
from .entity import LiteLLMEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LiteLLMConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LiteLLM TTS entities."""
    for subentry in config_entry.get_subentries_of_type("tts"):
        async_add_entities(
            [LiteLLMTTSEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LiteLLMTTSEntity(LiteLLMEntity, TextToSpeechEntity):
    """LiteLLM text-to-speech entity."""

    # The TTS manager needs an entity name to generate audio
    _attr_has_entity_name = False
    _attr_supported_languages = SUPPORTED_LANGUAGES
    # Unused, the speech endpoint takes no language
    _attr_default_language = "en-US"
    _attr_supported_options = [TextToSpeechCommonOption.VOICE]

    def __init__(self, entry: LiteLLMConfigEntry, subentry: ConfigSubentry) -> None:
        """Initialize the entity."""
        super().__init__(entry, subentry)
        self._attr_name = subentry.title
        # The TTS cache key holds the options, so a new model must change them
        self._attr_default_options = {
            CONF_MODEL: self.model,
            TextToSpeechCommonOption.VOICE: subentry.data[CONF_TTS_VOICE],
        }

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Generate speech with the speech endpoint."""
        coordinator = self.entry.runtime_data
        try:
            response = await coordinator.client.audio.speech.create(
                model=options[CONF_MODEL],
                voice=options[TextToSpeechCommonOption.VOICE],
                input=message,
                response_format="mp3",
            )
        except (AuthenticationError, PermissionDeniedError) as err:
            await coordinator.async_request_refresh()
            raise HomeAssistantError(f"Authentication error during TTS: {err}") from err
        except APIConnectionError as err:
            coordinator.mark_connection_error()
            raise HomeAssistantError(f"Connection error during TTS: {err}") from err
        except OpenAIError as err:
            coordinator.async_set_updated_data(None)
            raise HomeAssistantError(f"Error during TTS: {err}") from err

        coordinator.async_set_updated_data(None)
        return "mp3", response.content
