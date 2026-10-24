"""Tests for the Google Generative AI Conversation TTS entity."""

from collections.abc import Generator
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import wave

from google.genai import types
from google.genai.errors import APIError
from google.genai.voices import Voice, VoiceListResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_mock_service
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components import tts
from homeassistant.components.google_generative_ai_conversation.const import (
    CONF_CHAT_MODEL,
    DOMAIN,
    RECOMMENDED_TEMPERATURE,
)
from homeassistant.components.google_generative_ai_conversation.tts import ATTR_STYLE
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from tests.components.tts.common import retrieve_media

API_ERROR_500 = APIError("test", response_json={})
TEST_CHAT_MODEL = "models/some-tts-model"


@pytest.fixture(autouse=True)
def tts_mutagen_mock_fixture_autouse(tts_mutagen_mock: MagicMock) -> None:
    """Mock writing tags."""


@pytest.fixture(autouse=True)
def mock_tts_cache_dir_autouse(mock_tts_cache_dir: Path) -> None:
    """Mock the TTS cache dir with empty dir."""


@pytest.fixture
async def calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Mock media player calls."""
    return async_mock_service(hass, MP_DOMAIN, SERVICE_PLAY_MEDIA)


@pytest.fixture(autouse=True)
async def setup_internal_url(hass: HomeAssistant) -> None:
    """Set up internal url."""
    await async_process_ha_core_config(
        hass, {"internal_url": "http://example.local:8123"}
    )


@pytest.fixture
def mock_genai_client() -> Generator[AsyncMock]:
    """Mock genai_client."""
    client = Mock()
    client.aio.models.get = AsyncMock()
    client.aio.models.generate_content = AsyncMock(
        return_value=types.GenerateContentResponse(
            candidates=(
                types.Candidate(
                    content=types.Content(
                        parts=(
                            types.Part(
                                inline_data=types.Blob(
                                    data=b"raw-audio-bytes",
                                    mime_type="audio/L16;rate=24000",
                                )
                            ),
                        )
                    )
                ),
            )
        )
    )
    client.voices.list = Mock(return_value=VoiceListResponse(voices=[]))
    with patch(
        "homeassistant.components.google_generative_ai_conversation.Client",
        return_value=client,
    ) as mock_client:
        yield mock_client


@pytest.fixture(name="setup")
async def setup_fixture(
    hass: HomeAssistant,
    config: dict[str, Any],
    mock_genai_client: AsyncMock,
    request: pytest.FixtureRequest,
) -> None:
    """Set up the test environment.

    The chat model defaults to TEST_CHAT_MODEL; override it by indirectly
    parametrizing this fixture.
    """
    model = getattr(request, "param", TEST_CHAT_MODEL)
    config_entry = MockConfigEntry(domain=DOMAIN, data=config, version=2)
    config_entry.add_to_hass(hass)

    sub_entry = ConfigSubentry(
        data={
            tts.CONF_LANG: "en-US",
            CONF_CHAT_MODEL: model,
        },
        subentry_type="tts",
        title="Google AI TTS",
        subentry_id="test_subentry_tts_id",
        unique_id=None,
    )

    config_entry.runtime_data = mock_genai_client

    hass.config_entries.async_add_subentry(config_entry, sub_entry)
    await hass.config_entries.async_setup(config_entry.entry_id)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture(name="config")
def config_fixture() -> dict[str, Any]:
    """Return config."""
    return {
        CONF_API_KEY: "bla",
    }


@pytest.mark.parametrize(
    "service_data",
    [
        {
            ATTR_ENTITY_ID: "tts.google_ai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {},
        },
        {
            ATTR_ENTITY_ID: "tts.google_ai_tts",
            tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
            tts.ATTR_MESSAGE: "There is a person at the front door.",
            tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice2"},
        },
    ],
)
@pytest.mark.usefixtures("setup")
async def test_tts_service_speak(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
    service_data: dict[str, Any],
) -> None:
    """Test tts service."""

    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.aio.models.generate_content.reset_mock()

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.OK
    )
    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE, "zephyr")

    tts_entity._genai_client.aio.models.generate_content.assert_called_once_with(
        model=TEST_CHAT_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)
                )
            ),
            temperature=RECOMMENDED_TEMPERATURE,
        ),
    )


def _library_voice(voice_id: str, language_code: str) -> Voice:
    """Build a voice returned by the voices API."""
    return Voice(
        id=voice_id,
        display_name=voice_id.title(),
        gender="female",
        language_code=language_code,
        type="prebuilt",
    )


async def _reload_entry(hass: HomeAssistant) -> None:
    """Reload the config entry so the entity loads the voice library again."""
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("setup", ["models/gemini-3.8-flash-tts"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_tts_voice_library(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test the voice library is loaded page by page and grouped by language."""
    voices_list = mock_genai_client.return_value.voices.list
    voices_list.reset_mock()
    voices_list.side_effect = [
        VoiceListResponse(
            voices=[
                _library_voice("zephyr", "en-US"),
                _library_voice("ko-kr-advisor-1", "ko-KR"),
            ],
            next_page_token="page-2",
        ),
        VoiceListResponse(
            voices=[
                _library_voice("fr-fr-narrator-1", "fr-FR"),
                Voice(id="fr-fr-bare", language_code="fr-FR", type="prebuilt"),
                Voice(id="no-language", type="prebuilt"),
            ]
        ),
    ]
    await _reload_entry(hass)
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")

    assert [call.kwargs["page_token"] for call in voices_list.call_args_list] == [
        None,
        "page-2",
    ]
    assert all(
        call.kwargs["type_"] == ["prebuilt"] for call in voices_list.call_args_list
    )
    default_voices = entity.async_get_supported_voices("de-DE")
    assert len(default_voices) == 30
    assert entity.async_get_supported_voices("en-US") == default_voices
    assert entity.async_get_supported_voices("ko-KR") == [
        *default_voices,
        tts.Voice("ko-kr-advisor-1", "Ko-Kr-Advisor-1 (female)"),
    ]
    assert entity.async_get_supported_voices("fr-FR")[30:] == [
        tts.Voice("fr-fr-narrator-1", "Fr-Fr-Narrator-1 (female)"),
        tts.Voice("fr-fr-bare", "fr-fr-bare"),
    ]


@pytest.mark.parametrize("setup", ["models/gemini-3.8-flash-tts"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_tts_voice_library_error(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the prebuilt voices are kept when the voice library cannot be loaded."""
    mock_genai_client.return_value.voices.list.side_effect = RuntimeError("boom")
    await _reload_entry(hass)
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")

    assert "Could not load the Google AI voice library: boom" in caplog.text
    assert len(entity.async_get_supported_voices("ko-KR")) == 30


@pytest.mark.parametrize("setup", ["models/gemini-3.8-flash-tts"], indirect=True)
@pytest.mark.usefixtures("setup")
async def test_tts_voice_library_page_limit(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the voice library stops paging when the API never ends the listing."""
    voices_list = mock_genai_client.return_value.voices.list
    voices_list.reset_mock()
    voices_list.side_effect = None
    voices_list.return_value = VoiceListResponse(
        voices=[_library_voice("fr-fr-narrator-1", "fr-FR")],
        next_page_token="again",
    )
    await _reload_entry(hass)

    assert voices_list.call_count == 10
    assert "Stopped loading the Google AI voice library after 10 pages" in caplog.text


@pytest.mark.parametrize(
    "setup", ["gemini-3.1-flash-tts-preview", TEST_CHAT_MODEL], indirect=True
)
@pytest.mark.usefixtures("setup")
async def test_tts_voice_library_not_loaded_for_older_model(
    hass: HomeAssistant,
    mock_genai_client: AsyncMock,
) -> None:
    """Test models without voice library support do not query the voices API."""
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_genai_client.return_value.voices.list.assert_not_called()


@pytest.mark.usefixtures("setup")
async def test_tts_service_speak_error(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    calls: list[ServiceCall],
) -> None:
    """Test service call with HTTP response 500."""
    service_data = {
        ATTR_ENTITY_ID: "tts.google_ai_tts",
        tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
        tts.ATTR_MESSAGE: "There is a person at the front door.",
        tts.ATTR_OPTIONS: {tts.ATTR_VOICE: "voice1"},
    }
    tts_entity = hass.data[tts.DOMAIN].get_entity(service_data[ATTR_ENTITY_ID])
    tts_entity._genai_client.aio.models.generate_content.reset_mock()
    tts_entity._genai_client.aio.models.generate_content.side_effect = API_ERROR_500

    await hass.services.async_call(
        tts.DOMAIN,
        "speak",
        service_data,
        blocking=True,
    )

    assert len(calls) == 1
    assert (
        await retrieve_media(hass, hass_client, calls[0].data[ATTR_MEDIA_CONTENT_ID])
        == HTTPStatus.INTERNAL_SERVER_ERROR
    )

    voice_id = service_data[tts.ATTR_OPTIONS].get(tts.ATTR_VOICE)

    tts_entity._genai_client.aio.models.generate_content.assert_called_once_with(
        model=TEST_CHAT_MODEL,
        contents="There is a person at the front door.",
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_id)
                )
            ),
            temperature=RECOMMENDED_TEMPERATURE,
        ),
    )


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_supported_languages(hass: HomeAssistant) -> None:
    """Test the supported languages are unique and cover regional variants."""
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")
    languages = entity.supported_languages

    assert len(languages) == len(set(languages))
    assert {"en-US", "en-GB", "es-419", "kk-KZ", "yue-HK", "zh-CN", "zh-TW"} <= set(
        languages
    )


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("model", "sampling"),
    [
        ("gemini-2.5-flash-preview-tts", True),
        ("gemini-3.1-flash-tts-preview", True),
        ("gemini-3.8-flash-tts", False),
        ("models/gemini-3.8-flash-lite-tts", False),
        ("gemini-4-flash-tts-preview", False),
    ],
)
async def test_tts_wire_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_genai_transport: AsyncMock,
    model: str,
    sampling: bool,
) -> None:
    """TTS independently omits temperature, without adding thinking or changing voices."""
    subentry = mock_config_entry.subentries["ulid-tts"]
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data={**subentry.data, CONF_CHAT_MODEL: model}
    )
    await hass.async_block_till_done()
    mock_genai_transport.return_value = [
        {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "inlineData": {
                                    "data": "YXVkaW8=",
                                    "mimeType": "audio/L16;rate=24000",
                                }
                            }
                        ],
                    }
                }
            ]
        }
    ]
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")
    with patch(
        "homeassistant.components.google_generative_ai_conversation.tts.convert_to_wav",
        return_value=b"wav",
    ):
        assert await entity.async_get_tts_audio(
            "Hello", "en-US", {tts.ATTR_VOICE: "zephyr"}
        ) == ("wav", b"wav")
    config = mock_genai_transport.call_args.kwargs["http_request"].data[
        "generationConfig"
    ]
    assert ("temperature" in config) is sampling
    assert not {"thinkingConfig", "topP", "topK"}.intersection(config)
    assert config["responseModalities"] == ["AUDIO"]
    assert (
        config["speechConfig"]["voice_config"]["prebuilt_voice_config"]["voice_name"]
        == "zephyr"
    )


def _audio_response(mime_type: str) -> dict[str, Any]:
    """Build a raw generateContent response with audio."""
    return {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"inlineData": {"data": "YXVkaW8=", "mimeType": mime_type}}
                    ],
                }
            }
        ]
    }


@pytest.fixture
def wav_audio() -> bytes:
    """Create a complete WAV with known PCM samples."""
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(24000)
        audio.writeframes(b"\x00\x00\x01\x00\xff\x7f\x00\x80")
    return output.getvalue()


@pytest.mark.usefixtures("setup")
@pytest.mark.parametrize(
    ("mime_type", "header_size"),
    [("audio/wav", 0), ("audio/L16;rate=24000", 44)],
)
async def test_tts_audio_formats(
    hass: HomeAssistant,
    wav_audio: bytes,
    mime_type: str,
    header_size: int,
) -> None:
    """Preserve complete WAV output and wrap legacy PCM exactly once."""
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")
    response = entity._genai_client.aio.models.generate_content.return_value
    response.candidates[0].content.parts[0].inline_data = types.Blob(
        data=wav_audio[header_size:], mime_type=mime_type
    )

    audio_format, audio_data = await entity.async_get_tts_audio(
        "Hello", "en-US", dict(entity.default_options)
    )

    assert audio_format == "wav"
    assert audio_data == wav_audio
    with wave.open(BytesIO(audio_data), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getsampwidth() == 2
        assert audio.getframerate() == 24000
        assert audio.getnframes() == 4
        assert audio.readframes(4) == b"\x00\x00\x01\x00\xff\x7f\x00\x80"


@pytest.mark.usefixtures("mock_init_component")
@pytest.mark.parametrize(
    ("model", "expected_options"),
    [
        pytest.param(
            "gemini-3.8-flash-tts", [tts.ATTR_VOICE, ATTR_STYLE], id="flash_3_8"
        ),
        pytest.param(
            "models/gemini-3.8-flash-lite-tts",
            [tts.ATTR_VOICE, ATTR_STYLE],
            id="flash_lite_3_8",
        ),
        pytest.param(
            "gemini-3.1-flash-tts-preview", [tts.ATTR_VOICE], id="flash_3_1_preview"
        ),
        pytest.param(
            "gemini-2.5-flash-preview-tts", [tts.ATTR_VOICE], id="flash_2_5_preview"
        ),
    ],
)
async def test_tts_supported_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    model: str,
    expected_options: list[str],
) -> None:
    """Test the style option is only offered for models with speech metadata."""
    subentry = mock_config_entry.subentries["ulid-tts"]
    hass.config_entries.async_update_subentry(
        mock_config_entry, subentry, data={**subentry.data, CONF_CHAT_MODEL: model}
    )
    await hass.async_block_till_done()

    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")
    assert entity.supported_options == expected_options


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_style_wire_parameters(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_genai_transport: AsyncMock,
) -> None:
    """Test the style is sent as speech metadata instead of being part of the text."""
    subentry = mock_config_entry.subentries["ulid-tts"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_CHAT_MODEL: "gemini-3.8-flash-tts"},
    )
    await hass.async_block_till_done()
    mock_genai_transport.return_value = [_audio_response("audio/wav")]
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")

    await entity.async_get_tts_audio(
        "Hello", "en-US", {tts.ATTR_VOICE: "zephyr", ATTR_STYLE: "cheerful"}
    )

    body = mock_genai_transport.call_args.kwargs["http_request"].data
    assert body["contents"][0]["parts"] == [
        {"text": "Hello", "speechMetadata": {"style": "cheerful"}}
    ]


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_style_not_supported_by_model(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the style option is rejected for models without speech metadata."""
    subentry = mock_config_entry.subentries["ulid-tts"]
    hass.config_entries.async_update_subentry(
        mock_config_entry,
        subentry,
        data={**subentry.data, CONF_CHAT_MODEL: "gemini-3.1-flash-tts-preview"},
    )
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="style"):
        await hass.services.async_call(
            tts.DOMAIN,
            "speak",
            {
                ATTR_ENTITY_ID: "tts.google_ai_tts",
                tts.ATTR_MEDIA_PLAYER_ENTITY_ID: "media_player.something",
                tts.ATTR_MESSAGE: "Hello",
                tts.ATTR_OPTIONS: {ATTR_STYLE: "cheerful"},
            },
            blocking=True,
        )


@pytest.mark.usefixtures("setup")
async def test_tts_unsupported_audio_format(hass: HomeAssistant) -> None:
    """Keep unsupported audio formats as visible failures."""
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")
    response = entity._genai_client.aio.models.generate_content.return_value
    response.candidates[0].content.parts[0].inline_data = types.Blob(
        data=b"unsupported-audio", mime_type="audio/mpeg"
    )

    with pytest.raises(
        HomeAssistantError, match="Unsupported audio MIME type: audio/mpeg"
    ):
        await entity.async_get_tts_audio("Hello", "en-US", dict(entity.default_options))


@pytest.mark.usefixtures("mock_init_component")
async def test_tts_default_model(
    hass: HomeAssistant,
    mock_genai_transport: AsyncMock,
) -> None:
    """Test the recommended model is used when the subentry sets none."""
    mock_genai_transport.return_value = [_audio_response("audio/wav")]
    entity = hass.data[tts.DOMAIN].get_entity("tts.google_ai_tts")

    await entity.async_get_tts_audio("Hello", "en-US", dict(entity.default_options))

    request = mock_genai_transport.call_args.kwargs["http_request"]
    assert request.url.endswith("/models/gemini-3.8-flash-tts:generateContent")
