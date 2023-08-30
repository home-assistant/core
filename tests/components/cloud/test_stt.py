"""Test the speech-to-text platform for the cloud integration."""
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from hass_nabucasa.voice import STTResponse, VoiceError
import pytest

from homeassistant.components.cloud import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator


@pytest.mark.parametrize(
    ("mock_process_stt", "expected_response_data"),
    [
        (
            AsyncMock(return_value=STTResponse(True, "Turn the Kitchen Lights on")),
            {"text": "Turn the Kitchen Lights on", "result": "success"},
        ),
        (AsyncMock(side_effect=VoiceError("Boom!")), {"text": None, "result": "error"}),
    ],
)
async def test_cloud_speech(
    cloud: MagicMock,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_process_stt: AsyncMock,
    expected_response_data: dict[str, Any],
) -> None:
    """Test cloud text-to-speech."""
    cloud.voice.process_stt = mock_process_stt

    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()

    state = hass.states.get("stt.cloud")
    assert state
    assert state.state == STATE_UNKNOWN

    client = await hass_client()

    response = await client.post(
        "/api/stt/stt.cloud",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1;"
                " language=de-DE"
            )
        },
        data=b"Test",
    )
    response_data = await response.json()

    assert mock_process_stt.call_count == 1
    assert (
        mock_process_stt.call_args.kwargs["content_type"]
        == "audio/wav; codecs=audio/pcm; samplerate=16000"
    )
    assert mock_process_stt.call_args.kwargs["language"] == "de-DE"
    assert response.status == HTTPStatus.OK
    assert response_data == expected_response_data

    state = hass.states.get("stt.cloud")
    assert state
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
