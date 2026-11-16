"""Test the OpenRouter TTS entity."""

from http import HTTPStatus
import io
from unittest.mock import AsyncMock, MagicMock
import wave

from openai import OpenAIError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import tts
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.open_router.const import (
    CONF_TTS_SPEED,
    CONF_TTS_VOICE,
    DOMAIN,
)
from homeassistant.components.open_router.tts import OpenRouterTTSEntity
from homeassistant.components.tts import ATTR_VOICE
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.components.tts.common import retrieve_media


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


@pytest.mark.usefixtures("tts_mutagen_mock", "mock_tts_cache_dir")
async def test_speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_openai_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test speech is generated through Home Assistant with configured options."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )
    calls = async_mock_service(hass, MP_DOMAIN, SERVICE_PLAY_MEDIA)
    mock_config_entry.add_to_hass(hass)
    subentry = ConfigSubentry(
        data={
            CONF_MODEL: "openai/gpt-4o-mini-tts",
            "supported_voices": ["alloy", "echo"],
            CONF_TTS_VOICE: "echo",
            CONF_TTS_SPEED: 1.5,
        },
        subentry_type="tts",
        title="GPT-4o mini TTS",
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(mock_config_entry, subentry)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = "tts.gpt_4o_mini_tts"
    assert hass.states.get(entity_id).name == "GPT-4o mini TTS"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.config_entry_id == mock_config_entry.entry_id
    assert entity_entry.config_subentry_id == subentry.subentry_id

    mock_openai_client.audio.speech.create = AsyncMock(
        return_value=MagicMock(content=b"mp3data")
    )

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        {
            ATTR_ENTITY_ID: entity_id,
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
        },
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    mock_openai_client.audio.speech.create.assert_called_once_with(
        model="openai/gpt-4o-mini-tts",
        voice="echo",
        input="There is a person at the front door.",
        response_format="mp3",
        speed=1.5,
        extra_headers={
            "X-Title": "Home Assistant",
            "HTTP-Referer": "https://www.home-assistant.io/integrations/open_router",
        },
    )
