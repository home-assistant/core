"""
Tests for Rhasspy speech to text platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/integrations/rhasspy/
"""
import asyncio
import io
from unittest.mock import MagicMock, patch
import wave

import pytest

from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_platform(hass):
    """Set up rhasspy platform."""
    hass.loop.run_until_complete(
        async_setup_component(hass, "stt", {"stt": {"platform": "rhasspy"}})
    )


async def test_settings(hass, hass_client):
    """Test settings."""
    client = await hass_client()
    response = await client.get("/api/stt/rhasspy")
    assert response.status == 200


async def test_stt(hass, hass_client):
    """Test streaming."""
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

    with patch(
        "homeassistant.components.rhasspy.stt.RhasspyClient"
    ) as make_mock_rhasspyclient:
        mock_rhasspyclient = make_mock_rhasspyclient.return_value
        mock_rhasspyclient.stream_to_text = MagicMock(return_value=asyncio.Future())
        mock_rhasspyclient.stream_to_text.return_value.set_result(test_transcription)

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
