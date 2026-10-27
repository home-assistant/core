"""Tests for the Google Cloud TTS entity."""

from collections.abc import AsyncGenerator, AsyncIterator
import io
from typing import Any
from unittest.mock import AsyncMock, patch
import wave

from google.api_core.exceptions import GoogleAPIError, Unauthenticated
from google.cloud.texttospeech_v1.types import cloud_tts
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import tts
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import MockConfigEntry

TTS_ENTITY_ID = "tts.my_google_cloud_title"
CHIRP_VOICE = "en-US-Chirp3-HD-Achernar"


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_tts_from_service_account_info: AsyncMock,
) -> None:
    """Set up the Google Cloud integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()


def mock_streaming_synthesize(
    mock_api_tts: AsyncMock,
    audio_chunks: list[bytes],
    error: Exception | None = None,
    call_error: Exception | None = None,
) -> list[cloud_tts.StreamingSynthesizeRequest]:
    """Mock streaming synthesis and return the list of sent requests."""
    requests: list[cloud_tts.StreamingSynthesizeRequest] = []

    async def response_gen() -> AsyncGenerator[cloud_tts.StreamingSynthesizeResponse]:
        for chunk in audio_chunks:
            yield cloud_tts.StreamingSynthesizeResponse(audio_content=chunk)
        if error:
            raise error

    async def streaming_synthesize(
        request_gen: AsyncIterator[cloud_tts.StreamingSynthesizeRequest],
    ) -> AsyncGenerator[cloud_tts.StreamingSynthesizeResponse]:
        if call_error:
            raise call_error
        requests.extend([request async for request in request_gen])
        return response_gen()

    mock_api_tts.streaming_synthesize.side_effect = streaming_synthesize
    return requests


async def message_gen() -> AsyncGenerator[str]:
    """Yield a message in chunks that are not on sentence boundaries."""
    yield "Hello wor"
    yield "ld. How are"
    yield " you?"


async def stream_audio(
    hass: HomeAssistant, options: dict[str, Any], language: str = "en-US"
) -> bytes:
    """Stream a message through the TTS entity and return the audio."""
    stream = tts.async_create_stream(hass, TTS_ENTITY_ID, language, options=options)
    stream.async_set_message_stream(message_gen())
    return b"".join([chunk async for chunk in stream.async_stream_result()])


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("options", "language"),
    [
        pytest.param({}, "en-US", id="defaults"),
        pytest.param({"speed": 1.5}, "en-US", id="speed"),
        pytest.param({}, "el-GR", id="language_from_voice"),
    ],
)
async def test_stream_tts_audio(
    hass: HomeAssistant,
    mock_api_tts: AsyncMock,
    options: dict[str, Any],
    language: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test streaming synthesis with a Chirp 3: HD voice."""
    requests = mock_streaming_synthesize(mock_api_tts, [bytes(100), bytes(200)])

    data = await stream_audio(
        hass,
        {**options, "voice": CHIRP_VOICE, tts.ATTR_PREFERRED_FORMAT: "wav"},
        language,
    )

    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 24000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1
        assert wav_file.readframes(150) == bytes(300)
    assert requests == snapshot
    mock_api_tts.synthesize_speech.assert_not_called()


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    "options",
    [
        pytest.param({}, id="no_voice"),
        pytest.param({"voice": "en-US-Standard-A"}, id="standard_voice"),
        pytest.param({"voice": CHIRP_VOICE, "pitch": 2.0}, id="pitch"),
        pytest.param({"voice": CHIRP_VOICE, "gain": 2.0}, id="gain"),
        pytest.param(
            {"voice": CHIRP_VOICE, "profiles": ["telephony-class-application"]},
            id="profiles",
        ),
        pytest.param({"voice": CHIRP_VOICE, "text_type": "ssml"}, id="ssml"),
    ],
)
async def test_stream_tts_audio_not_supported(
    hass: HomeAssistant,
    mock_api_tts: AsyncMock,
    options: dict[str, Any],
) -> None:
    """Test the message is synthesized at once if streaming is not supported."""
    mock_api_tts.synthesize_speech.return_value = cloud_tts.SynthesizeSpeechResponse(
        audio_content=b"mp3 audio"
    )

    data = await stream_audio(hass, options)

    assert data == b"mp3 audio"
    mock_api_tts.streaming_synthesize.assert_not_called()
    mock_api_tts.synthesize_speech.assert_called_once()


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("error", "call_error"),
    [
        pytest.param(GoogleAPIError("error"), None, id="response"),
        pytest.param(None, GoogleAPIError("error"), id="call"),
    ],
)
async def test_stream_tts_audio_error(
    hass: HomeAssistant,
    mock_api_tts: AsyncMock,
    error: Exception | None,
    call_error: Exception | None,
) -> None:
    """Test an error during streaming synthesis."""
    mock_streaming_synthesize(mock_api_tts, [bytes(100)], error, call_error)

    with pytest.raises(
        HomeAssistantError, match="Error occurred during Google Cloud TTS call"
    ):
        await stream_audio(
            hass, {"voice": CHIRP_VOICE, tts.ATTR_PREFERRED_FORMAT: "wav"}
        )


@pytest.mark.usefixtures("setup_integration")
async def test_stream_tts_audio_unauthenticated(
    hass: HomeAssistant,
    mock_api_tts: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth is started when the credentials are rejected."""
    mock_streaming_synthesize(mock_api_tts, [], call_error=Unauthenticated("error"))

    with (
        patch.object(mock_config_entry, "async_start_reauth") as mock_start_reauth,
        pytest.raises(HomeAssistantError),
    ):
        await stream_audio(
            hass, {"voice": CHIRP_VOICE, tts.ATTR_PREFERRED_FORMAT: "wav"}
        )

    mock_start_reauth.assert_called_once_with(hass)


@pytest.mark.usefixtures("setup_integration")
async def test_stream_tts_audio_invalid_options(
    hass: HomeAssistant,
    mock_api_tts: AsyncMock,
) -> None:
    """Test invalid options."""
    with pytest.raises(HomeAssistantError):
        await stream_audio(hass, {"voice": "invalid"})

    mock_api_tts.streaming_synthesize.assert_not_called()
    mock_api_tts.synthesize_speech.assert_not_called()
