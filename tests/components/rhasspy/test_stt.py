"""
Tests for Rhasspy speech to text platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import io
import wave

import pytest

from homeassistant.setup import async_setup_component

SPEECH_URL = "http://localhost:12101/api/speech-to-text"


@pytest.fixture(autouse=True)
def setup_platform(hass):
    """Set up rhasspy platform."""
    hass.loop.run_until_complete(
        async_setup_component(
            hass, "stt", {"stt": {"platform": "rhasspy", "speech_url": SPEECH_URL}}
        )
    )


async def test_settings(hass, hass_client):
    """Test settings."""
    client = await hass_client()
    response = await client.get("/api/stt/rhasspy")
    assert response.status == 200


async def test_stt(hass, hass_client, aioclient_mock):
    """Test WAV endpoint."""
    test_transcription = "this is a test"

    # Create fake WAV file
    with io.BytesIO() as wav_io:
        # Can't use context manager because of pylint
        wav_file: wave.Wave_write = wave.open(wav_io, mode="wb")
        wav_file.setframerate(16000)
        wav_file.setsampwidth(2)
        wav_file.setnchannels(1)
        wav_file.writeframes(b"Test")
        wav_file.close()

        wav_data = wav_io.getvalue()

    aioclient_mock.post(SPEECH_URL, status=200, text=test_transcription)

    client = await hass_client()
    response = await client.post(
        "/api/stt/rhasspy",
        headers={
            "X-Speech-Content": "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1; language=en-US"
        },
        data=wav_data,
    )
    response_data = await response.json()

    assert response.status == 200
    assert response_data == {"text": test_transcription, "result": "success"}
