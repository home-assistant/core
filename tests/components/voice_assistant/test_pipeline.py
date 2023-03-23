"""Pipeline tests for Voice Assistant integration."""
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.voice_assistant.pipeline import (
    AudioPipelineRequest,
    Pipeline,
    PipelineEventType,
    PipelineRun,
)
from homeassistant.core import Context
from homeassistant.setup import async_setup_component

from tests.components.tts.conftest import (  # noqa: F401, pylint: disable=unused-import
    mock_get_cache_files,
    mock_init_cache_dir,
)


@pytest.fixture(autouse=True)
async def init_components(hass):
    """Initialize relevant components with empty configs."""
    assert await async_setup_component(hass, "voice_assistant", {})


@pytest.fixture
async def mock_get_tts_audio(hass):
    """Set up media source."""
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

    with patch(
        "homeassistant.components.demo.tts.DemoProvider.get_tts_audio",
        return_value=("mp3", b""),
    ) as mock_get_tts:
        yield mock_get_tts


async def test_audio_pipeline(hass, mock_get_tts_audio):
    """Run audio pipeline with mock TTS."""
    pipeline = Pipeline(
        name="test",
        language=hass.config.language,
        conversation_engine=None,
        tts_engine=None,
    )

    event_callback = MagicMock()
    await AudioPipelineRequest(intent_input="Are the lights on?").execute(
        PipelineRun(
            hass,
            context=Context(),
            pipeline=pipeline,
            event_callback=event_callback,
            language=hass.config.language,
        )
    )

    calls = event_callback.mock_calls
    assert calls[0].args[0].type == PipelineEventType.RUN_START
    assert calls[0].args[0].data == {
        "pipeline": "test",
        "language": hass.config.language,
    }

    assert calls[1].args[0].type == PipelineEventType.INTENT_START
    assert calls[1].args[0].data == {
        "engine": "default",
        "intent_input": "Are the lights on?",
    }
    assert calls[2].args[0].type == PipelineEventType.INTENT_FINISH
    assert calls[2].args[0].data == {
        "intent_output": {
            "conversation_id": None,
            "response": {
                "card": {},
                "data": {"code": "no_intent_match"},
                "language": hass.config.language,
                "response_type": "error",
                "speech": {
                    "plain": {
                        "extra_data": None,
                        "speech": "Sorry, I couldn't understand that",
                    }
                },
            },
        }
    }

    assert calls[3].args[0].type == PipelineEventType.TTS_START
    assert calls[3].args[0].data == {
        "engine": "default",
        "tts_input": "Sorry, I couldn't understand that",
    }
    assert calls[4].args[0].type == PipelineEventType.TTS_FINISH
    assert (
        calls[4].args[0].data["tts_output"]
        == f"/api/tts_proxy/dae2cdcb27a1d1c3b07ba2c7db91480f9d4bfd8f_{hass.config.language}_-_demo.mp3"
    )

    assert calls[5].args[0].type == PipelineEventType.RUN_FINISH
