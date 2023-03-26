"""Websocket tests for Voice Assistant integration."""
import asyncio
from collections.abc import AsyncIterable
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    mock_get_cache_files,
    mock_init_cache_dir,
)
from tests.typing import WebSocketGenerator

_TRANSCRIPT = "test transcript"


class MockSttProvider(stt.Provider):
    """Mock STT provider."""

    def __init__(self, hass: HomeAssistant, text: str) -> None:
        """Init test provider."""
        self.hass = hass
        self.text = text

    @property
    def supported_languages(self) -> list[str]:
        """Return a list of supported languages."""
        return [self.hass.config.language]

    @property
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV]

    @property
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM]

    @property
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bitrates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported samplerates."""
        return [stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Process an audio stream."""
        return stt.SpeechResult(self.text, stt.SpeechResultState.SUCCESS)


@pytest.fixture(autouse=True)
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "media_source", {})
    assert await async_setup_component(
        hass,
        "tts",
        {
            "tts": {
                "platform": "demo",
            }
        },
    )
    assert await async_setup_component(hass, "stt", {})

    # mock_platform fails because it can't import
    hass.data[stt.DOMAIN] = {"test": MockSttProvider(hass, _TRANSCRIPT)}

    assert await async_setup_component(hass, "voice_assistant", {})

    with patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=("mp3", b""),
    ) as mock_get_tts:
        yield mock_get_tts


async def test_text_only_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test events from a pipeline run with text input (no STT/TTS)."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "voice_assistant/run",
            "start_stage": "intent",
            "end_stage": "intent",
            "input": {"text": "Are the lights on?"},
        }
    )

    # result
    msg = await client.receive_json()
    assert msg["success"]

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"
    assert msg["event"]["data"] == {
        "pipeline": hass.config.language,
        "language": hass.config.language,
    }

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"
    assert msg["event"]["data"] == {
        "engine": "default",
        "intent_input": "Are the lights on?",
    }

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-end"
    assert msg["event"]["data"] == {
        "intent_output": {
            "response": {
                "speech": {
                    "plain": {
                        "speech": "Sorry, I couldn't understand that",
                        "extra_data": None,
                    }
                },
                "card": {},
                "language": "en",
                "response_type": "error",
                "data": {"code": "no_intent_match"},
            },
            "conversation_id": None,
        }
    }

    # run end
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-end"
    assert msg["event"]["data"] == {}


async def test_audio_pipeline(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test events from a pipeline run with audio input/output."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "voice_assistant/run",
            "start_stage": "stt",
            "end_stage": "tts",
        }
    )

    # result
    msg = await client.receive_json()
    assert msg["success"]

    # handler id
    msg = await client.receive_json()
    assert msg["event"]["handler_id"] == 1

    # run start
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-start"
    assert msg["event"]["data"] == {
        "pipeline": hass.config.language,
        "language": hass.config.language,
    }

    # stt
    msg = await client.receive_json()
    assert msg["event"]["type"] == "stt-start"
    assert msg["event"]["data"] == {
        "engine": "default",
        "metadata": {
            "bit_rate": 16,
            "channel": 1,
            "codec": "pcm",
            "format": "wav",
            "language": "en",
            "sample_rate": 16000,
        },
    }

    # End of audio stream (handler id + empty payload)
    await client.send_bytes(b"1")

    msg = await client.receive_json()
    assert msg["event"]["type"] == "stt-end"
    assert msg["event"]["data"] == {
        "stt_output": {"text": _TRANSCRIPT},
    }

    # intent
    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-start"
    assert msg["event"]["data"] == {
        "engine": "default",
        "intent_input": _TRANSCRIPT,
    }

    msg = await client.receive_json()
    assert msg["event"]["type"] == "intent-end"
    assert msg["event"]["data"] == {
        "intent_output": {
            "response": {
                "speech": {
                    "plain": {
                        "speech": "Sorry, I couldn't understand that",
                        "extra_data": None,
                    }
                },
                "card": {},
                "language": "en",
                "response_type": "error",
                "data": {"code": "no_intent_match"},
            },
            "conversation_id": None,
        }
    }

    # text to speech
    msg = await client.receive_json()
    assert msg["event"]["type"] == "tts-start"
    assert msg["event"]["data"] == {
        "engine": "default",
        "tts_input": "Sorry, I couldn't understand that",
    }

    msg = await client.receive_json()
    assert msg["event"]["type"] == "tts-end"
    assert msg["event"]["data"] == {
        "tts_output": {
            "url": f"/api/tts_proxy/dae2cdcb27a1d1c3b07ba2c7db91480f9d4bfd8f_{hass.config.language}_-_demo.mp3",
            "mime_type": "audio/mpeg",
        },
    }

    # run end
    msg = await client.receive_json()
    assert msg["event"]["type"] == "run-end"
    assert msg["event"]["data"] == {}


async def test_intent_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test partial pipeline run with conversation agent timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_converse(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.conversation.async_converse",
        new=sleepy_converse,
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
                "timeout": 0.00001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": hass.config.language,
            "language": hass.config.language,
        }

        # intent
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "intent_input": "Are the lights on?",
        }

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"


async def test_text_pipeline_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test text-only pipeline run with immediate timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_run(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.voice_assistant.pipeline.PipelineInput._execute",
        new=sleepy_run,
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
                "timeout": 0.0001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"


async def test_intent_failed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test text-only pipeline run with conversation agent error."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.conversation.async_converse",
        new=MagicMock(return_value=RuntimeError),
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "intent",
                "end_stage": "intent",
                "input": {"text": "Are the lights on?"},
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": hass.config.language,
            "language": hass.config.language,
        }

        # intent start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "intent-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "intent_input": "Are the lights on?",
        }

        # intent error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "intent-failed"


async def test_audio_pipeline_timeout(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test audio pipeline run with immediate timeout."""
    client = await hass_ws_client(hass)

    async def sleepy_run(*args, **kwargs):
        await asyncio.sleep(3600)

    with patch(
        "homeassistant.components.voice_assistant.pipeline.PipelineInput._execute",
        new=sleepy_run,
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
                "timeout": 0.0001,
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # handler id
        msg = await client.receive_json()
        assert msg["event"]["handler_id"] == 1

        # timeout error
        msg = await client.receive_json()
        assert not msg["success"]
        assert msg["error"]["code"] == "timeout"


async def test_stt_provider_missing(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test events from a pipeline run with a non-existent STT provider."""
    with patch(
        "homeassistant.components.stt.async_get_provider",
        new=MagicMock(return_value=None),
    ):
        client = await hass_ws_client(hass)

        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # handler id
        msg = await client.receive_json()
        assert msg["event"]["handler_id"] == 1

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": hass.config.language,
            "language": hass.config.language,
        }

        # stt
        msg = await client.receive_json()
        assert msg["event"]["type"] == "stt-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "metadata": {
                "bit_rate": 16,
                "channel": 1,
                "codec": "pcm",
                "format": "wav",
                "language": "en",
                "sample_rate": 16000,
            },
        }

        # End of audio stream (handler id + empty payload)
        await client.send_bytes(b"1")

        # stt error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "stt-provider-missing"


async def test_stt_stream_failed(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test events from a pipeline run with a non-existent STT provider."""
    with patch(
        "tests.components.voice_assistant.test_websocket.MockSttProvider.async_process_audio_stream",
        new=MagicMock(side_effect=RuntimeError),
    ):
        client = await hass_ws_client(hass)

        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "stt",
                "end_stage": "tts",
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # handler id
        msg = await client.receive_json()
        assert msg["event"]["handler_id"] == 1

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": hass.config.language,
            "language": hass.config.language,
        }

        # stt
        msg = await client.receive_json()
        assert msg["event"]["type"] == "stt-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "metadata": {
                "bit_rate": 16,
                "channel": 1,
                "codec": "pcm",
                "format": "wav",
                "language": "en",
                "sample_rate": 16000,
            },
        }

        # End of audio stream (handler id + empty payload)
        await client.send_bytes(b"1")

        # stt error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "stt-stream-failed"


async def test_tts_failed(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test pipeline run with text to speech error."""
    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        new=MagicMock(return_value=RuntimeError),
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "voice_assistant/run",
                "start_stage": "tts",
                "end_stage": "tts",
                "input": {"text": "Lights are on."},
            }
        )

        # result
        msg = await client.receive_json()
        assert msg["success"]

        # run start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "run-start"
        assert msg["event"]["data"] == {
            "pipeline": hass.config.language,
            "language": hass.config.language,
        }

        # tts start
        msg = await client.receive_json()
        assert msg["event"]["type"] == "tts-start"
        assert msg["event"]["data"] == {
            "engine": "default",
            "tts_input": "Lights are on.",
        }

        # tts error
        msg = await client.receive_json()
        assert msg["event"]["type"] == "error"
        assert msg["event"]["data"]["code"] == "tts-failed"


async def test_invalid_stage_order(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, init_components
) -> None:
    """Test pipeline run with invalid stage order."""
    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 5,
            "type": "voice_assistant/run",
            "start_stage": "tts",
            "end_stage": "stt",
            "input": {"text": "Lights are on."},
        }
    )

    # result
    msg = await client.receive_json()
    assert not msg["success"]
