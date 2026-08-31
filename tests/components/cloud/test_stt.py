"""Test the speech-to-text platform for the cloud integration."""

from collections.abc import AsyncGenerator
from copy import deepcopy
from http import HTTPStatus
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, patch

from hass_nabucasa import SpeechToTextV2Error
from hass_nabucasa.voice import STTResponse, VoiceError
import pytest

from homeassistant.components.assist_pipeline.pipeline import (  # pylint: disable=home-assistant-component-root-import
    STORAGE_KEY,
)
from homeassistant.components.cloud.const import DOMAIN, PREVIEW_FEATURE_STT_V2
from homeassistant.components.labs import async_update_preview_feature
from homeassistant.components.stt import (
    DEFAULT_AUDIO_PROCESSING,
    SpeechAudioProcessing,
    async_get_speech_to_text_entity,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import PIPELINE_DATA

from tests.typing import ClientSessionGenerator

ENTITY_ID = "stt.home_assistant_cloud"


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


@pytest.fixture(name="setup_stt")
async def setup_stt_fixture(hass: HomeAssistant, cloud: MagicMock) -> None:
    """Set up the cloud speech-to-text entity with labs available."""
    assert await async_setup_component(hass, "labs", {})
    assert await async_setup_component(hass, DOMAIN, {"cloud": {}})
    await hass.async_block_till_done()

    on_start_callback = cloud.register_on_start.call_args[0][0]
    await on_start_callback()


async def _process_audio(
    hass_client: ClientSessionGenerator, language: str = "de-DE"
) -> dict[str, Any]:
    """Post an audio stream to the cloud speech-to-text entity."""
    client = await hass_client()
    response = await client.post(
        f"/api/stt/{ENTITY_ID}",
        headers={
            "X-Speech-Content": (
                "format=wav; codec=pcm; sample_rate=16000; bit_rate=16; channel=1;"
                f" language={language}"
            )
        },
        data=b"Test",
    )

    assert response.status == HTTPStatus.OK
    return await response.json()


@pytest.mark.usefixtures("setup_stt")
async def test_stt_v2_disabled_by_default(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that audio goes to the legacy service while the lab is off."""
    cloud.voice.process_stt = AsyncMock(return_value=STTResponse(True, "Lights on"))
    cloud.stt_v2.process_stt = AsyncMock()

    assert await _process_audio(hass_client) == {
        "text": "Lights on",
        "result": "success",
    }
    assert cloud.voice.process_stt.call_count == 1
    cloud.stt_v2.process_stt.assert_not_called()

    entity = async_get_speech_to_text_entity(hass, ENTITY_ID)
    assert entity
    assert entity.audio_processing == DEFAULT_AUDIO_PROCESSING


@pytest.mark.usefixtures("setup_stt")
async def test_stt_v2_enabled(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that audio goes to the v2 service while the lab is on."""
    cloud.voice.process_stt = AsyncMock()
    cloud.stt_v2.process_stt = AsyncMock(return_value=STTResponse(True, "Lights on"))

    await async_update_preview_feature(hass, DOMAIN, PREVIEW_FEATURE_STT_V2, True)

    assert await _process_audio(hass_client) == {
        "text": "Lights on",
        "result": "success",
    }
    cloud.voice.process_stt.assert_not_called()
    assert cloud.stt_v2.process_stt.call_count == 1
    assert cloud.stt_v2.process_stt.call_args.kwargs == {
        "stream": ANY,
        "language": "de-DE",
        "audio_format": "wav",
        "codec": "pcm",
        "bit_rate": 16,
        "sample_rate": 16000,
        "channel": 1,
    }

    entity = async_get_speech_to_text_entity(hass, ENTITY_ID)
    assert entity
    assert entity.audio_processing == SpeechAudioProcessing(
        requires_external_vad=True,
        prefers_auto_gain_enabled=False,
        prefers_noise_reduction_enabled=False,
    )


@pytest.mark.usefixtures("setup_stt")
async def test_stt_v2_falls_back_on_unsupported_language(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test that a language v2 lacks still uses the legacy service."""
    cloud.voice.process_stt = AsyncMock(return_value=STTResponse(True, "Lights on"))
    cloud.stt_v2.process_stt = AsyncMock()

    await async_update_preview_feature(hass, DOMAIN, PREVIEW_FEATURE_STT_V2, True)

    assert await _process_audio(hass_client, language="hy-AM") == {
        "text": "Lights on",
        "result": "success",
    }
    assert cloud.voice.process_stt.call_count == 1
    cloud.stt_v2.process_stt.assert_not_called()


@pytest.mark.parametrize(
    "mock_process_stt",
    [
        AsyncMock(side_effect=SpeechToTextV2Error("Boom!")),
        AsyncMock(return_value=STTResponse(False, None)),
    ],
    ids=["error", "no-speech"],
)
@pytest.mark.usefixtures("setup_stt")
async def test_stt_v2_failure(
    hass: HomeAssistant,
    cloud: MagicMock,
    hass_client: ClientSessionGenerator,
    mock_process_stt: AsyncMock,
) -> None:
    """Test that a failure of the v2 service is reported as an error."""
    cloud.stt_v2.process_stt = mock_process_stt

    await async_update_preview_feature(hass, DOMAIN, PREVIEW_FEATURE_STT_V2, True)

    assert await _process_audio(hass_client) == {"text": None, "result": "error"}


@pytest.mark.usefixtures("setup_stt")
async def test_stt_v2_disconnects_when_turned_off(
    hass: HomeAssistant, cloud: MagicMock
) -> None:
    """Test that turning the lab off closes the connection to the v2 service."""
    cloud.stt_v2.disconnect = AsyncMock()

    await async_update_preview_feature(hass, DOMAIN, PREVIEW_FEATURE_STT_V2, True)
    await hass.async_block_till_done()

    cloud.stt_v2.disconnect.assert_not_called()

    await async_update_preview_feature(hass, DOMAIN, PREVIEW_FEATURE_STT_V2, False)
    await hass.async_block_till_done()

    cloud.stt_v2.disconnect.assert_awaited_once()
