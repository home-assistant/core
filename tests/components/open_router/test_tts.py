"""Test the OpenRouter TTS entity."""

import io
from unittest.mock import AsyncMock, MagicMock
import wave

from openai import OpenAIError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.open_router.const import CONF_TTS_VOICE, DOMAIN
from homeassistant.components.open_router.tts import OpenRouterTTSEntity
from homeassistant.components.tts import ATTR_VOICE
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


def _create_entity(
    hass: HomeAssistant, client: MagicMock, model: str = "openai/gpt-4o-mini-tts"
) -> OpenRouterTTSEntity:
    """Create an OpenRouter TTS entity with a mocked client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "bla"},
        subentries_data=[
            ConfigSubentryData(
                data={
                    CONF_MODEL: model,
                    "supported_voices": ["alloy", "echo"],
                    CONF_TTS_VOICE: "echo",
                },
                subentry_id="tts_subentry",
                subentry_type="tts",
                title="OpenRouter TTS",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    entry.runtime_data = client

    return OpenRouterTTSEntity(entry, entry.subentries["tts_subentry"])


def _mock_client(content: bytes) -> MagicMock:
    """Create a client that returns the given audio content."""
    client = MagicMock()
    client.audio.speech.create = AsyncMock(return_value=MagicMock(content=content))
    return client


async def test_default_options_use_configured_voice(
    hass: HomeAssistant,
) -> None:
    """Test the configured voice is used when model voices are available."""
    entity = _create_entity(hass, MagicMock())

    assert entity.default_options == {"voice": "echo"}


async def test_entity_inherits_device_name(hass: HomeAssistant) -> None:
    """Test the entity has no name of its own."""
    entity = _create_entity(hass, MagicMock())

    assert entity.name is None


async def test_does_not_support_streaming_input(hass: HomeAssistant) -> None:
    """Test the entity uses the non-streaming input contract."""
    entity = _create_entity(hass, MagicMock())

    assert not entity.async_supports_streaming_input()


async def test_get_tts_audio_mp3(hass: HomeAssistant) -> None:
    """Test MP3 audio is requested and returned as is."""
    client = _mock_client(b"mp3data")
    entity = _create_entity(hass, client)

    assert await entity.async_get_tts_audio(
        "Hello world", "en", {ATTR_VOICE: "echo"}
    ) == ("mp3", b"mp3data")
    client.audio.speech.create.assert_called_once_with(
        model="openai/gpt-4o-mini-tts",
        voice="echo",
        input="Hello world",
        response_format="mp3",
        speed=1.0,
        extra_headers={
            "X-Title": "Home Assistant",
            "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        },
    )


@pytest.mark.parametrize(
    "model",
    [
        pytest.param("google/gemini-2.5-flash-preview-tts", id="gemini"),
        pytest.param("heygen/voice", id="heygen"),
    ],
)
async def test_get_tts_audio_pcm_only_model(hass: HomeAssistant, model: str) -> None:
    """Test PCM is requested for PCM-only providers and wrapped in WAV."""
    client = _mock_client(b"\x00\x01" * 10)
    entity = _create_entity(hass, client, model)

    extension, data = await entity.async_get_tts_audio(
        "Hello world", "en", {ATTR_VOICE: "echo"}
    )

    assert client.audio.speech.create.call_args.kwargs["response_format"] == "pcm"
    assert extension == "wav"
    with wave.open(io.BytesIO(data), "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1
        assert wav_file.readframes(wav_file.getnframes()) == b"\x00\x01" * 10


async def test_get_tts_audio_raises_on_api_error(
    hass: HomeAssistant,
) -> None:
    """Test an OpenAI error is surfaced as a HomeAssistantError."""
    client = MagicMock()
    client.audio.speech.create = AsyncMock(side_effect=OpenAIError)
    entity = _create_entity(hass, client)

    with pytest.raises(HomeAssistantError):
        await entity.async_get_tts_audio("Hello world", "en", {ATTR_VOICE: "echo"})
