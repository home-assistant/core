"""Constants for the Testing of the ElevenLabs text-to-speech integration."""

from elevenlabs.types import LanguageResponse, Model, Voice

from homeassistant.components.elevenlabs.const import DEFAULT_MODEL

MOCK_VOICES = [
    Voice(
        voice_id="voice1",
        name="Voice 1",
    ),
    Voice(
        voice_id="voice2",
        name="Voice 2",
    ),
]

MOCK_MODELS = [
    Model(
        model_id="model1",
        name="Model 1",
        can_do_text_to_speech=True,
        languages=[
            LanguageResponse(language_id="en", name="English"),
            LanguageResponse(language_id="de", name="German"),
            LanguageResponse(language_id="es", name="Spanish"),
            LanguageResponse(language_id="ja", name="Japanese"),
        ],
    ),
    Model(
        model_id="model2",
        name="Model 2",
        can_do_text_to_speech=True,
        languages=[
            LanguageResponse(language_id="en", name="English"),
            LanguageResponse(language_id="de", name="German"),
            LanguageResponse(language_id="es", name="Spanish"),
            LanguageResponse(language_id="ja", name="Japanese"),
        ],
    ),
    Model(
        model_id=DEFAULT_MODEL,
        name=DEFAULT_MODEL,
        can_do_text_to_speech=True,
        languages=[
            LanguageResponse(language_id="en", name="English"),
            LanguageResponse(language_id="de", name="German"),
            LanguageResponse(language_id="es", name="Spanish"),
            LanguageResponse(language_id="ja", name="Japanese"),
        ],
    ),
]
