"""Test the speech-to-text platform for the cloud integration."""

from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from hass_nabucasa.voice import STTResponse, VoiceError
import pytest
from typing_extensions import AsyncGenerator

from homeassistant.components.assist_pipeline.pipeline import STORAGE_KEY
from homeassistant.components.cloud.const import DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import PIPELINE_DATA

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def delay_save_fixture() -> AsyncGenerator[None]:
    """Load the homeassistant integration."""
    with patch("homeassistant.helpers.collection.SAVE_DELAY", new=0):
        yield


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
    hass: HomeAssistant,
    cloud: MagicMock,
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

    state = hass.states.get("stt.home_assistant_cloud")
    assert state
    assert state.state == STATE_UNKNOWN

    client = await hass_client()

    response = await client.post(
        "/api/stt/stt.home_assistant_cloud",
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

    state = hass.states.get("stt.home_assistant_cloud")
    assert state
    assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


async def test_migrating_pipelines(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_storage: dict[str, Any],
) -> None:
    """Test migrating pipelines when cloud stt entity is added."""
    entity_id = "stt.home_assistant_cloud"
    cloud.voice.process_stt = AsyncMock(
        return_value=STTResponse(True, "Turn the Kitchen Lights on")
    )
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": "assist_pipeline.pipelines",
        "data": deepcopy(PIPELINE_DATA),
    }

    assert await async_setup_component(hass, "assist_pipeline", {})
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    await cloud.login("test-user", "test-pass")
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_UNKNOWN

    # The stt/tts engines should have been updated to the new cloud engine ids.
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["stt_engine"] == entity_id
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_engine"]
        == "tts.home_assistant_cloud"
    )

    # The other items should stay the same.
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["conversation_engine"]
        == "conversation_engine_1"
    )
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["conversation_language"]
        == "language_1"
    )
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["id"]
        == "01GX8ZWBAQYWNB1XV3EXEZ75DY"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["language"] == "language_1"
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["name"] == "Home Assistant Cloud"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["stt_language"] == "language_1"
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_language"] == "language_1"
    assert (
        hass_storage[STORAGE_KEY]["data"]["items"][0]["tts_voice"]
        == "Arnold Schwarzenegger"
    )
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["wake_word_entity"] is None
    assert hass_storage[STORAGE_KEY]["data"]["items"][0]["wake_word_id"] is None
    assert hass_storage[STORAGE_KEY]["data"]["items"][1] == PIPELINE_DATA["items"][1]
    assert hass_storage[STORAGE_KEY]["data"]["items"][2] == PIPELINE_DATA["items"][2]
