"""Test tts."""

import io
import re
from unittest.mock import patch
import wave

import pytest
from syrupy.assertion import SnapshotAssertion
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.error import Error
from wyoming.tts import SynthesizeStopped

from homeassistant.components import tts, wyoming
from homeassistant.components.wyoming.coordinator import UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util import dt as dt_util

from . import TTS_INFO_LANGUAGE_REPLACED, TTS_INFO_NEW_VOICE, MockAsyncTcpClient

from tests.common import async_fire_time_changed


async def test_support(hass: HomeAssistant, init_wyoming_tts) -> None:
    """Test supported properties."""
    state = hass.states.get("tts.test_tts")
    assert state is not None

    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None

    assert entity.supported_languages == ["en-US"]
    assert entity.supported_options == [
        tts.ATTR_AUDIO_OUTPUT,
        tts.ATTR_VOICE,
        wyoming.ATTR_SPEAKER,
    ]
    voices = entity.async_get_supported_voices("en-US")
    assert len(voices) == 1
    assert voices[0].name == "Test Voice"
    assert voices[0].voice_id == "Test Voice"
    assert not entity.async_get_supported_voices("de-DE")


async def test_voices_refreshed(
    hass: HomeAssistant, init_wyoming_tts: ConfigEntry
) -> None:
    """Test that a voice added on the service becomes available."""
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None
    assert entity.async_get_supported_voices("de-DE") is None

    with patch(
        "homeassistant.components.wyoming.coordinator.load_wyoming_info",
        return_value=TTS_INFO_NEW_VOICE,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert set(entity.supported_languages) == {"en-US", "de-DE"}
    voices = entity.async_get_supported_voices("de-DE")
    assert voices is not None
    assert [voice.voice_id for voice in voices] == ["New Voice"]

    # Adding a language must not move the default away from a supported one.
    assert entity.default_language == "en-US"

    # Refreshed info is shared with the rest of the integration.
    assert init_wyoming_tts.runtime_data.service.info == TTS_INFO_NEW_VOICE


@pytest.mark.usefixtures("init_wyoming_tts")
async def test_default_language_follows_removed_language(
    hass: HomeAssistant,
) -> None:
    """Test that the default language moves when the current one is removed."""
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None
    assert entity.default_language == "en-US"

    with patch(
        "homeassistant.components.wyoming.coordinator.load_wyoming_info",
        return_value=TTS_INFO_LANGUAGE_REPLACED,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert entity.supported_languages == ["de-DE"]
    assert entity.default_language == "de-DE"


@pytest.mark.usefixtures("init_wyoming_tts")
async def test_voices_kept_when_refresh_fails(hass: HomeAssistant) -> None:
    """Test that the last known voices are kept when a refresh fails."""
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None

    with patch(
        "homeassistant.components.wyoming.coordinator.load_wyoming_info",
        return_value=None,
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
        await hass.async_block_till_done()

    assert entity.supported_languages == ["en-US"]
    voices = entity.async_get_supported_voices("en-US")
    assert voices is not None
    assert [voice.voice_id for voice in voices] == ["Test Voice"]


async def test_get_tts_audio(
    hass: HomeAssistant, init_wyoming_tts, snapshot: SnapshotAssertion
) -> None:
    """Test get audio."""
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_tts")
    assert entity is not None
    assert not entity.async_supports_streaming_input()

    audio = bytes(100)

    # Verify audio
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass,
                "Hello world",
                "tts.test_tts",
                "en-US",
                options={tts.ATTR_PREFERRED_FORMAT: "wav"},
            ),
        )

    assert extension == "wav"
    assert data is not None
    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1

        # nframes = 0 due to streaming
        assert len(data) == len(audio) + 44  # WAVE header is 44 bytes
        assert data[44:] == audio

    assert mock_client.written == snapshot


async def test_get_tts_audio_different_formats(
    hass: HomeAssistant, init_wyoming_tts, snapshot: SnapshotAssertion
) -> None:
    """Test changing preferred audio format."""
    audio = bytes(16000 * 2 * 1)  # one second
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    # Request a different sample rate, etc.
    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass,
                "Hello world",
                "tts.test_tts",
                "en-US",
                options={
                    tts.ATTR_PREFERRED_FORMAT: "wav",
                    tts.ATTR_PREFERRED_SAMPLE_RATE: 48000,
                    tts.ATTR_PREFERRED_SAMPLE_CHANNELS: 2,
                },
            ),
        )

    assert extension == "wav"
    assert data is not None
    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 48000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 2

    assert mock_client.written == snapshot

    # MP3 is the default
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass,
                "Hello world",
                "tts.test_tts",
                "en-US",
            ),
        )

    assert extension == "mp3"
    assert b"ID3" in data
    assert mock_client.written == snapshot


async def test_get_tts_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test streaming audio and losing connection."""
    stream = tts.async_create_stream(hass, "tts.test_tts", "en-US")
    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        stream.async_set_message("Hello world")
        with pytest.raises(HomeAssistantError):
            async for _chunk in stream.async_stream_result():
                pass


async def test_get_tts_audio_audio_oserror(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test get audio and error raising."""
    audio = bytes(100)
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    mock_client = MockAsyncTcpClient(audio_events)

    with (
        patch(
            "homeassistant.components.wyoming.tts.AsyncTcpClient",
            mock_client,
        ),
        patch.object(mock_client, "read_event", side_effect=OSError("Boom!")),
        pytest.raises(
            HomeAssistantError,
        ),
    ):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass, "Hello world", "tts.test_tts", hass.config.language
            ),
        )


@pytest.mark.usefixtures("init_wyoming_tts")
@pytest.mark.parametrize(
    ("error_code", "expected_message"),
    [
        pytest.param(None, "Error from Wyoming service: Boom!", id="without_code"),
        pytest.param(
            "VoiceNotFoundError",
            "Error from Wyoming service: Boom! (code: VoiceNotFoundError)",
            id="with_code",
        ),
    ],
)
async def test_get_tts_audio_error_event(
    hass: HomeAssistant, error_code: str | None, expected_message: str
) -> None:
    """Test that an error event from the service is reported."""
    with (
        patch(
            "homeassistant.components.wyoming.tts.AsyncTcpClient",
            MockAsyncTcpClient([Error(text="Boom!", code=error_code).event()]),
        ),
        pytest.raises(HomeAssistantError, match=re.escape(expected_message)),
    ):
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(hass, "Hello world", "tts.test_tts", "en-US"),
        )


@pytest.mark.usefixtures("init_wyoming_streaming_tts")
async def test_get_tts_audio_streaming_error_event(hass: HomeAssistant) -> None:
    """Test that an error event received while streaming is reported."""

    async def message_gen():
        yield "Hello world."

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient([Error(text="Boom!").event()]),
    ):
        stream = tts.async_create_stream(
            hass,
            "tts.test_streaming_tts",
            "en-US",
            options={tts.ATTR_PREFERRED_FORMAT: "wav"},
        )
        stream.async_set_message_stream(message_gen())

        with pytest.raises(
            HomeAssistantError, match="Error from Wyoming service: Boom!"
        ):
            async for _chunk in stream.async_stream_result():
                pass


async def test_voice_speaker(
    hass: HomeAssistant, init_wyoming_tts, snapshot: SnapshotAssertion
) -> None:
    """Test using a different voice and speaker."""
    audio = bytes(100)
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        await tts.async_get_media_source_audio(
            hass,
            tts.generate_media_source_id(
                hass,
                "Hello world",
                "tts.test_tts",
                "en-US",
                options={tts.ATTR_VOICE: "voice1", wyoming.ATTR_SPEAKER: "speaker1"},
            ),
        )
        assert mock_client.written == snapshot


async def test_get_tts_audio_streaming(
    hass: HomeAssistant, init_wyoming_streaming_tts, snapshot: SnapshotAssertion
) -> None:
    """Test get audio with streaming."""
    entity = hass.data[DATA_INSTANCES]["tts"].get_entity("tts.test_streaming_tts")
    assert entity is not None
    assert entity.async_supports_streaming_input()

    audio = bytes(100)

    # Verify audio
    audio_events = [
        AudioStart(rate=16000, width=2, channels=1).event(),
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
        SynthesizeStopped().event(),
    ]

    async def message_gen():
        yield "Hello "
        yield "Word."

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        stream = tts.async_create_stream(
            hass,
            "tts.test_streaming_tts",
            "en-US",
            options={tts.ATTR_PREFERRED_FORMAT: "wav"},
        )
        stream.async_set_message_stream(message_gen())
        data = b"".join([chunk async for chunk in stream.async_stream_result()])

        # Ensure client was disconnected properly
        assert mock_client.is_connected is False

    assert data is not None
    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1
        assert wav_file.getnframes() == 0  # streaming
        assert data[44:] == audio  # WAV header is 44 bytes

    assert mock_client.written == snapshot
