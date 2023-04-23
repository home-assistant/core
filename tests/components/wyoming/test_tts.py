"""Test tts."""
from __future__ import annotations

import io
from unittest.mock import patch
import wave

from wyoming.audio import AudioChunk, AudioStop

from homeassistant.components import tts
from homeassistant.core import HomeAssistant

from . import MockAsyncTcpClient


async def test_support(hass: HomeAssistant, init_wyoming_tts) -> None:
    """Test supported properties."""
    state = hass.states.get("tts.test_tts")
    assert state is not None

    entity = tts.async_get_text_to_speech_entity(hass, "tts.test_tts")
    assert entity is not None

    assert entity.supported_languages == ["en-US"]
    assert entity.supported_options == [tts.ATTR_AUDIO_OUTPUT, tts.ATTR_VOICE]
    assert entity.async_get_supported_voices("en-US") == [
        tts.Voice(
            voice_id="Test Voice",
            name="Test Voice",
        )
    ]
    assert not entity.async_get_supported_voices("de-DE")


async def test_get_tts_audio(hass: HomeAssistant, init_wyoming_tts, snapshot) -> None:
    """Test get audio."""
    entity = tts.async_get_text_to_speech_entity(hass, "tts.test_tts")
    assert entity is not None

    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await entity.async_get_tts_audio(
            "Hello world", hass.config.language
        )

    assert extension == "wav"
    assert data is not None
    with io.BytesIO(data) as wav_io, wave.open(wav_io, "rb") as wav_file:
        assert wav_file.getframerate() == 16000
        assert wav_file.getsampwidth() == 2
        assert wav_file.getnchannels() == 1
        assert wav_file.readframes(wav_file.getnframes()) == audio

    assert mock_client.written == snapshot


async def test_get_tts_audio_raw(
    hass: HomeAssistant, init_wyoming_tts, snapshot
) -> None:
    """Test get raw audio."""
    entity = tts.async_get_text_to_speech_entity(hass, "tts.test_tts")
    assert entity is not None

    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient(audio_events),
    ) as mock_client:
        extension, data = await entity.async_get_tts_audio(
            "Hello world",
            hass.config.language,
            options={tts.ATTR_AUDIO_OUTPUT: "raw"},
        )

    assert extension == "raw"
    assert data == audio
    assert mock_client.written == snapshot


async def test_get_tts_audio_connection_lost(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test streaming audio and losing connection."""
    entity = tts.async_get_text_to_speech_entity(hass, "tts.test_tts")
    assert entity is not None

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        MockAsyncTcpClient([None]),
    ):
        extension, data = await entity.async_get_tts_audio(
            "Hello world", hass.config.language
        )

    assert extension is None
    assert data is None


async def test_get_tts_audio_audio_oserror(
    hass: HomeAssistant, init_wyoming_tts
) -> None:
    """Test get audio and error raising."""
    entity = tts.async_get_text_to_speech_entity(hass, "tts.test_tts")
    assert entity is not None

    audio = bytes(100)
    audio_events = [
        AudioChunk(audio=audio, rate=16000, width=2, channels=1).event(),
        AudioStop().event(),
    ]

    mock_client = MockAsyncTcpClient(audio_events)

    with patch(
        "homeassistant.components.wyoming.tts.AsyncTcpClient",
        mock_client,
    ), patch.object(mock_client, "read_event", side_effect=OSError("Boom!")):
        extension, data = await entity.async_get_tts_audio(
            "Hello world", hass.config.language
        )

    assert extension is None
    assert data is None
