"""Test Azure OpenAI capability lookups."""

import pytest

from homeassistant.components.azure_openai.capabilities import (
    DEFAULT_STT_API_VERSION,
    MODEL_CAPABILITIES,
    STT_MODEL_FAMILIES,
    TTS_MODEL_FAMILIES,
    get_tts_voices,
)


@pytest.mark.parametrize(
    "family",
    [
        "gpt-5-pro",
        "gpt-5.4-pro",
        "gpt-5-codex",
        "gpt-5.1-codex",
        "gpt-5.1-codex-mini",
        "gpt-5.1-codex-max",
        "gpt-5.2-codex",
        "gpt-5.3-codex",
    ],
)
def test_code_interpreter_not_offered_for_pro_and_codex(family: str) -> None:
    """Test families Azure excludes from the code interpreter tool."""
    assert "code" not in MODEL_CAPABILITIES[family].features


@pytest.mark.parametrize(
    "family",
    [
        "o1",
        "o4-mini",
        "gpt-4.1-mini",
        "gpt-5-mini",
        "gpt-5-codex",
        "gpt-5.1-codex",
        "gpt-5.1-codex-mini",
        "gpt-5.1-codex-max",
        "gpt-5.2-codex",
        "gpt-5.3-codex",
    ],
)
def test_image_generation_not_offered_for_unsupported_families(family: str) -> None:
    """Test families Azure excludes from the image generation tool."""
    assert "image" not in MODEL_CAPABILITIES[family].features


@pytest.mark.parametrize(
    ("family", "feature"),
    [
        ("gpt-4o", "code"),
        ("gpt-4o", "image"),
        ("gpt-4.1-mini", "code"),
        ("o3-mini", "code"),
        ("o3-mini", "image"),
        ("gpt-5", "code"),
        ("gpt-5-pro", "image"),
        ("gpt-5.4-pro", "image"),
        ("gpt-5-nano", "image"),
        ("gpt-5.1", "code"),
        ("gpt-6-astra", "code"),
        ("gpt-6-astra", "image"),
    ],
)
def test_documented_hosted_tools_are_offered(family: str, feature: str) -> None:
    """Test families keep the hosted tools their model reference documents."""
    assert feature in MODEL_CAPABILITIES[family].features


@pytest.mark.parametrize("family", ["o1-mini", "computer-use-preview"])
def test_unsupported_families_offer_no_hosted_tools(family: str) -> None:
    """Test families outside the Responses API expose no hosted tools."""
    assert not MODEL_CAPABILITIES[family].features & {"code", "image"}


def test_stt_model_families_match_azure_deployment_models() -> None:
    """Test the selector lists Azure's deployable transcription model IDs."""
    assert STT_MODEL_FAMILIES == ("whisper", "gpt-4o-transcribe")


def test_default_stt_api_version() -> None:
    """Test transcription requests use the latest confirmed classic API."""
    assert DEFAULT_STT_API_VERSION == "2025-03-01-preview"


def test_tts_model_families_match_azure_deployment_models() -> None:
    """Test the selector lists Azure's deployable speech model IDs."""
    assert TTS_MODEL_FAMILIES == ("gpt-4o-mini-tts", "tts", "tts-hd")


def test_get_tts_voices_gpt_model() -> None:
    """Test the steerable speech model offers the complete voice set."""
    assert get_tts_voices("gpt-4o-mini-tts-preview-2025-12-15") == (
        "marin",
        "cedar",
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
    )


@pytest.mark.parametrize("model", ["tts", "tts-hd", "future-speech-model"])
def test_get_tts_voices_uses_v1_compatible_set(model: str) -> None:
    """Test older and unknown models use the common v1 voice set."""
    assert get_tts_voices(model) == (
        "alloy",
        "ash",
        "coral",
        "echo",
        "fable",
        "onyx",
        "nova",
        "sage",
        "shimmer",
    )
