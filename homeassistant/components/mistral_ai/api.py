"""Low-level helpers for the Mistral AI API."""

from typing import Any

from mistralai.client import Mistral
from mistralai.client.types import UNSET
import mistralai.client.utils.security  # noqa: F401

# Capability required per subentry type when listing available models.
CAPABILITY_BY_TYPE: dict[str, str] = {
    "conversation": "completion_chat",
    "stt": "audio_transcription",
    "tts": "audio_speech",
}

SUBENTRY_TYPES = ("conversation", "stt", "tts")


def is_unset(value: Any) -> bool:
    """Return whether a value is the SDK UNSET sentinel."""
    return isinstance(value, type(UNSET))


def fetch_models(client: Mistral) -> list[Any]:
    """Fetch the list of available models from the Mistral API."""
    return client.models.list(timeout_ms=10_000).data or []


def get_model_ids(api_key: str, capability: str) -> list[str]:
    """Return the model IDs supporting a given capability."""
    client = Mistral(api_key=api_key)
    _ = client.models

    return sorted(
        model.id
        for model in fetch_models(client)
        if getattr(getattr(model, "capabilities", None), capability, False)
    )


def model_status_from_list(models: list[Any], model_id: str) -> dict[str, Any]:
    """Return the deprecation status of a model from the model list."""
    for model in models:
        if model.id != model_id:
            continue

        deprecation = model.deprecation
        replacement = model.deprecation_replacement_model

        if is_unset(deprecation) or deprecation is None:
            return {
                "id": model.id,
                "status": "active",
                "deprecation": None,
                "deprecation_replacement_model": None,
            }

        return {
            "id": model.id,
            "status": "deprecated",
            "deprecation": deprecation.isoformat(),
            "deprecation_replacement_model": (
                replacement
                if not is_unset(replacement) and replacement is not None
                else None
            ),
        }

    return {"id": model_id, "status": "unknown"}


async def get_voices(client: Mistral) -> list[tuple[str, str]]:
    """Fetch the preset voices available for text-to-speech."""
    response = await client.audio.voices.search_async(type_="preset")
    voices = response.result.data if response and response.result else []
    return [
        (voice.id, voice.name)
        for voice in voices
        if getattr(voice, "type", None) == "preset"
    ]
