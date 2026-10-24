"""Test agent manager."""

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import Mock, PropertyMock, patch

import pytest

from homeassistant.components import tts
from homeassistant.components.conversation import (
    ConversationAudioInput,
    ConversationResult,
    async_converse,
    async_get_agent_info,
    trace,
)
from homeassistant.components.conversation.default_agent import DefaultAgent
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.intent import IntentResponse


async def test_async_converse(hass: HomeAssistant, init_components) -> None:
    """Test the async_converse method."""
    context = Context()
    with patch(
        "homeassistant.components.conversation.default_agent.DefaultAgent.async_process",
        return_value=ConversationResult(response=IntentResponse(language="test lang")),
    ) as mock_process:
        await async_converse(
            hass,
            text="test command",
            conversation_id="test id",
            context=context,
            language="test lang",
            agent_id="conversation.home_assistant",
            device_id="test device id",
            extra_system_prompt="test extra prompt",
        )

    assert mock_process.called
    conversation_input = mock_process.call_args[0][0]
    assert conversation_input.text == "test command"
    assert conversation_input.conversation_id == "test id"
    assert conversation_input.context is context
    assert conversation_input.language == "test lang"
    assert conversation_input.agent_id == "conversation.home_assistant"
    assert conversation_input.device_id == "test device id"
    assert conversation_input.extra_system_prompt == "test extra prompt"


async def _audio_stream() -> AsyncGenerator[bytes]:
    """Yield spoken audio."""
    yield b"audio"


async def test_async_converse_audio(hass: HomeAssistant, init_components) -> None:
    """Test sending spoken audio to an agent and getting its spoken response."""
    audio = ConversationAudioInput(
        pcm_format=tts.PcmFormat(sample_rate=16000, sample_width=2, channels=1),
        stream=_audio_stream(),
    )
    audio_output = Mock()

    with (
        patch.object(
            DefaultAgent,
            "supports_audio_input",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch.object(
            DefaultAgent,
            "supports_audio_output",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch(
            "homeassistant.components.conversation.default_agent.DefaultAgent.async_process",
            return_value=ConversationResult(
                response=IntentResponse(language="test lang")
            ),
        ) as mock_process,
    ):
        agent_info = async_get_agent_info(hass, "conversation.home_assistant")
        assert agent_info is not None
        assert agent_info.supports_audio_input
        assert agent_info.supports_audio_output

        await async_converse(
            hass,
            text="",
            conversation_id="test id",
            context=Context(),
            agent_id="conversation.home_assistant",
            audio=audio,
            audio_output=audio_output,
        )

    conversation_input = mock_process.call_args[0][0]
    assert conversation_input.text == ""
    assert conversation_input.audio is audio
    assert conversation_input.audio_output is audio_output

    # The trace has the format of the audio, not the audio itself
    last_trace = trace.async_get_traces()[-1].as_dict()
    assert last_trace["events"][0]["data"]["audio"] == {
        "pcm_format": {"sample_rate": 16000, "sample_width": 2, "channels": 1}
    }


@pytest.mark.parametrize(
    ("audio_kwargs", "message"),
    [
        pytest.param(
            {
                "audio": ConversationAudioInput(
                    pcm_format=tts.PcmFormat(
                        sample_rate=16000, sample_width=2, channels=1
                    ),
                    stream=_audio_stream(),
                )
            },
            "does not support audio input",
            id="audio_input",
        ),
        pytest.param(
            {"audio_output": Mock()},
            "does not support audio output",
            id="audio_output",
        ),
    ],
)
async def test_async_converse_audio_not_supported(
    hass: HomeAssistant,
    init_components,
    audio_kwargs: dict[str, Any],
    message: str,
) -> None:
    """Test agents only get spoken audio if they support it."""
    with pytest.raises(ValueError, match=message):
        await async_converse(
            hass,
            text="",
            conversation_id=None,
            context=Context(),
            agent_id="conversation.home_assistant",
            **audio_kwargs,
        )
