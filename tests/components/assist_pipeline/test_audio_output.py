"""Tests for Assist pipeline audio output."""

import asyncio
from collections.abc import AsyncGenerator
from dataclasses import FrozenInstanceError
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components import assist_pipeline, stt
from homeassistant.components.assist_pipeline.audio_output import (
    PipelineAudioOutput,
    PipelineAudioOutputError,
    PipelineAudioOutputManager,
)
from homeassistant.components.assist_pipeline.error import PipelineRunValidationError
from homeassistant.components.assist_pipeline.run import _PipelineProcessorRequest
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import chat_session, llm
from homeassistant.util.json import JsonObjectType

from tests.typing import ClientSessionGenerator


async def _collect(output: PipelineAudioOutput) -> bytes:
    """Collect a pipeline audio output."""
    return b"".join([chunk async for chunk in output.async_stream_result()])


async def test_bounded_stream_and_successful_close(hass: HomeAssistant) -> None:
    """Test output is bounded and a successful close drains all data."""
    manager = PipelineAudioOutputManager(hass)
    output = manager.async_create("wav", "audio/wav", buffer_size=1)

    await output.async_write(b"one")
    blocked_write = hass.async_create_task(output.async_write(b"two"))
    await asyncio.sleep(0)
    assert not blocked_write.done()

    consumer = hass.async_create_task(_collect(output))
    await blocked_write
    output.async_close()

    assert await consumer == b"onetwo"
    with pytest.raises(RuntimeError, match="closed"):
        await output.async_write(b"three")


async def test_stream_failure_propagates(hass: HomeAssistant) -> None:
    """Test producer failures propagate to the consumer."""
    manager = PipelineAudioOutputManager(hass)
    output = manager.async_create("wav", "audio/wav")
    consumer = hass.async_create_task(_collect(output))
    await asyncio.sleep(0)

    output.async_fail(ValueError("audio generation failed"))

    with pytest.raises(PipelineAudioOutputError, match="audio generation failed"):
        await consumer


async def test_stream_allows_one_consumer(hass: HomeAssistant) -> None:
    """Test only one consumer can read an output."""
    manager = PipelineAudioOutputManager(hass)
    output = manager.async_create("wav", "audio/wav")
    output.async_close()

    assert await _collect(output) == b""
    with pytest.raises(RuntimeError, match="already has a consumer"):
        await _collect(output)


async def test_audio_output_http_view(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    init_components: None,
) -> None:
    """Test unauthenticated HEAD and GET access to an output."""
    output = hass.data[assist_pipeline.DOMAIN].audio_output_manager.async_create(
        "wav", "audio/wav"
    )
    await output.async_write(b"audio")
    output.async_close()
    client = await hass_client_no_auth()

    head_response = await client.head(output.url)
    assert head_response.status == HTTPStatus.OK
    assert head_response.content_type == "audio/wav"

    get_response = await client.get(output.url)
    assert get_response.status == HTTPStatus.OK
    assert get_response.content_type == "audio/wav"
    assert await get_response.read() == b"audio"

    missing_response = await client.get(f"{output.url}-missing")
    assert missing_response.status == HTTPStatus.NOT_FOUND


async def test_legacy_tts_stream_fallback(
    hass: HomeAssistant,
    init_components: None,
) -> None:
    """Test stream lookup falls back to the existing TTS manager."""
    legacy_stream = Mock()
    with patch(
        "homeassistant.components.assist_pipeline.tts.async_get_stream",
        return_value=legacy_stream,
    ) as get_tts_stream:
        assert (
            assist_pipeline.async_get_audio_output_stream(hass, "legacy-token")
            is legacy_stream
        )

    get_tts_stream.assert_called_once_with(hass, "legacy-token")


class _StreamingTestProcessor:
    """Test-only streaming audio-to-audio processor."""

    def __init__(self, host: Any) -> None:
        """Initialize the processor."""
        self.host = host
        self.response_audio = host.async_create_response_audio("wav", "audio/wav")
        self.supports_streaming_response = True
        self.start_response_immediately = True
        self.request: _PipelineProcessorRequest | None = None
        self.finished = False
        self.cleanup = Mock()

    async def async_validate(self, request: _PipelineProcessorRequest) -> None:
        """Capture and validate the private request."""
        self.request = request
        assert request.stt_metadata is not None
        assert request.stt_stream is not None

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Transform input chunks into deterministic output chunks."""
        assert request is self.request
        assert request.stt_stream is not None
        async for chunk in request.stt_stream:
            await self.response_audio.async_write(b"response:" + chunk)
        self.response_audio.async_close()
        self.finished = True

    def invalidate(self) -> None:
        """Invalidate processing."""


class _TestPipelineTool(llm.Tool):
    """Tool used by the audio-to-audio processor test."""

    name = "test__pipeline_tool"
    description = "Return the pipeline tool context"

    def __init__(self) -> None:
        """Initialize the tool."""
        self.llm_context: llm.LLMContext | None = None

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> JsonObjectType:
        """Return context that proves the call was scoped to the run."""
        self.llm_context = llm_context
        return {
            "argument": tool_input.tool_args["argument"],
            "device_id": llm_context.device_id,
            "user_id": llm_context.context.user_id if llm_context.context else None,
        }


class _ToolCallingStreamingTestProcessor(_StreamingTestProcessor):
    """Audio-to-audio processor that calls a Home Assistant tool."""

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Consume audio, call a tool, and stream its result."""
        assert request.stt_stream is not None
        async for _chunk in request.stt_stream:
            pass

        tool_host = await self.host.async_get_tool_host()
        assert [tool.name for tool in tool_host.tools] == ["test__pipeline_tool"]
        result = await tool_host.async_call_tool(
            llm.ToolInput(
                tool_name="test__pipeline_tool",
                tool_args={"argument": "called"},
            )
        )
        await self.response_audio.async_write(
            f"{result['argument']}:{result['device_id']}".encode()
        )
        self.response_audio.async_close()
        self.finished = True


async def test_private_audio_to_audio_processor(
    hass: HomeAssistant,
    init_components: None,
    mock_chat_session: chat_session.ChatSession,
) -> None:
    """Test private processor audio streams concurrently through the controller."""
    events: list[assist_pipeline.PipelineEvent] = []
    consumed_while_running = False
    consumer_task: asyncio.Task[bytes] | None = None
    processor: _StreamingTestProcessor | None = None

    async def audio_data() -> AsyncGenerator[bytes]:
        yield b"one"
        yield b"two"

    async def consume(output: PipelineAudioOutput) -> bytes:
        nonlocal consumed_while_running
        chunks = []
        async for chunk in output.async_stream_result():
            assert processor is not None
            consumed_while_running |= not processor.finished
            chunks.append(chunk)
        return b"".join(chunks)

    def process_event(event: assist_pipeline.PipelineEvent) -> None:
        nonlocal consumer_task
        events.append(event)
        if event.type is assist_pipeline.PipelineEventType.RUN_START:
            assert event.data is not None
            output = assist_pipeline.async_get_audio_output_stream(
                hass, event.data["tts_output"]["token"]
            )
            assert isinstance(output, PipelineAudioOutput)
            consumer_task = hass.async_create_task(consume(output))

    def create_processor(run) -> _StreamingTestProcessor:
        nonlocal processor
        processor = _StreamingTestProcessor(run)
        return processor

    with patch(
        "homeassistant.components.assist_pipeline.run._create_pipeline_processor",
        side_effect=create_processor,
    ):
        pipeline_input = assist_pipeline.pipeline.PipelineInput(
            run=assist_pipeline.pipeline.PipelineRun(
                hass,
                context=Context(),
                pipeline=assist_pipeline.pipeline.async_get_pipeline(hass),
                start_stage=assist_pipeline.PipelineStage.STT,
                end_stage=assist_pipeline.PipelineStage.TTS,
                event_callback=process_event,
            ),
            session=mock_chat_session,
            stt_metadata=stt.SpeechMetadata(
                language="en",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_data(),
            wake_word_phrase="okay nabu",
            conversation_extra_system_prompt="Be concise",
            device_id="device-id",
            satellite_id="satellite.test",
        )
        await pipeline_input.execute(validate=True)

    assert processor is not None
    assert processor.request is not None
    with pytest.raises(FrozenInstanceError):
        processor.request.device_id = "other"  # type: ignore[misc]
    assert consumer_task is not None
    assert await consumer_task == b"response:oneresponse:two"
    assert consumed_while_running
    assert [event.type for event in events] == [
        assist_pipeline.PipelineEventType.RUN_START,
        assist_pipeline.PipelineEventType.RUN_END,
    ]
    assert events[0].data == {
        "pipeline": pipeline_input.run.pipeline.id,
        "language": pipeline_input.run.language,
        "conversation_id": mock_chat_session.conversation_id,
        "satellite_id": "satellite.test",
        "tts_output": {
            "token": processor.response_audio.token,
            "url": processor.response_audio.url,
            "mime_type": "audio/wav",
            "start_streaming": True,
            "stream_response": True,
        },
    }


async def test_audio_to_audio_processor_calls_run_scoped_tool(
    hass: HomeAssistant,
    init_components: None,
    mock_chat_session: chat_session.ChatSession,
) -> None:
    """Test an audio processor can call a tool with the run's authorization."""
    context = Context(user_id="test-user")
    tool = _TestPipelineTool()
    api_instance = llm.APIInstance(
        api=Mock(hass=hass, id="test-api", name="Test API"),
        api_prompt="Use the test tool",
        llm_context=llm.LLMContext(
            platform="unused",
            context=None,
            language=None,
            assistant="unused",
            device_id=None,
        ),
        tools=[tool],
    )
    processor: _ToolCallingStreamingTestProcessor | None = None
    consumer_task: asyncio.Task[bytes] | None = None

    async def audio_data() -> AsyncGenerator[bytes]:
        yield b"audio"

    def create_processor(run) -> _ToolCallingStreamingTestProcessor:
        nonlocal processor
        processor = _ToolCallingStreamingTestProcessor(run)
        return processor

    def process_event(event: assist_pipeline.PipelineEvent) -> None:
        nonlocal consumer_task
        if event.type is assist_pipeline.PipelineEventType.RUN_START:
            assert processor is not None
            consumer_task = hass.async_create_task(_collect(processor.response_audio))

    async def get_api(
        _hass: HomeAssistant,
        _api_id: str | list[str],
        llm_context: llm.LLMContext,
    ) -> llm.APIInstance:
        api_instance.llm_context = llm_context
        return api_instance

    with (
        patch(
            "homeassistant.components.assist_pipeline.run._create_pipeline_processor",
            side_effect=create_processor,
        ),
        patch(
            "homeassistant.components.assist_pipeline.tool_host.llm.async_get_api",
            new_callable=AsyncMock,
            side_effect=get_api,
        ) as get_api,
    ):
        pipeline_input = assist_pipeline.pipeline.PipelineInput(
            run=assist_pipeline.pipeline.PipelineRun(
                hass,
                context=context,
                pipeline=assist_pipeline.pipeline.async_get_pipeline(hass),
                start_stage=assist_pipeline.PipelineStage.STT,
                end_stage=assist_pipeline.PipelineStage.TTS,
                event_callback=process_event,
                llm_api_id="test-api",
            ),
            session=mock_chat_session,
            stt_metadata=stt.SpeechMetadata(
                language="en",
                format=stt.AudioFormats.WAV,
                codec=stt.AudioCodecs.PCM,
                bit_rate=stt.AudioBitRates.BITRATE_16,
                sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                channel=stt.AudioChannels.CHANNEL_MONO,
            ),
            stt_stream=audio_data(),
            device_id="device-id",
        )
        await pipeline_input.execute(validate=True)

    assert consumer_task is not None
    assert await consumer_task == b"called:device-id"
    get_api.assert_awaited_once()
    llm_context = get_api.await_args.args[2]
    assert llm_context.context is context
    assert llm_context.language == pipeline_input.run.language
    assert llm_context.assistant == "conversation"
    assert llm_context.device_id == "device-id"
    assert tool.llm_context is llm_context


class _FailingStreamingTestProcessor(_StreamingTestProcessor):
    """Test processor that fails after creating its output."""

    async def async_validate(self, request: _PipelineProcessorRequest) -> None:
        """Accept the request."""
        self.request = request

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Fail pipeline processing."""
        raise PipelineRunValidationError("processor failed")


class _FailingValidationTestProcessor(_StreamingTestProcessor):
    """Test processor that fails validation."""

    async def async_validate(self, request: _PipelineProcessorRequest) -> None:
        """Reject the request."""
        raise PipelineRunValidationError("validation failed")


class _BlockingStreamingTestProcessor(_FailingStreamingTestProcessor):
    """Test processor that waits until cancelled."""

    def __init__(self, host: Any) -> None:
        """Initialize the processor."""
        super().__init__(host)
        self.started = asyncio.Event()

    async def async_execute(self, request: _PipelineProcessorRequest) -> None:
        """Wait indefinitely."""
        self.started.set()
        await asyncio.Event().wait()


async def test_pipeline_error_fails_audio_output(
    hass: HomeAssistant,
    init_components: None,
    mock_chat_session: chat_session.ChatSession,
) -> None:
    """Test a pipeline error terminates a controller-owned output."""
    processor: _FailingStreamingTestProcessor | None = None

    def create_processor(run) -> _FailingStreamingTestProcessor:
        nonlocal processor
        processor = _FailingStreamingTestProcessor(run)
        return processor

    with patch(
        "homeassistant.components.assist_pipeline.run._create_pipeline_processor",
        side_effect=create_processor,
    ):
        pipeline_input = assist_pipeline.pipeline.PipelineInput(
            run=assist_pipeline.pipeline.PipelineRun(
                hass,
                context=Context(),
                pipeline=assist_pipeline.pipeline.async_get_pipeline(hass),
                start_stage=assist_pipeline.PipelineStage.INTENT,
                end_stage=assist_pipeline.PipelineStage.INTENT,
                event_callback=lambda _event: None,
            ),
            session=mock_chat_session,
            intent_input="test",
        )
        await pipeline_input.execute(validate=True)

    assert processor is not None
    processor.cleanup.assert_called_once()
    with pytest.raises(PipelineAudioOutputError, match="processor failed"):
        await _collect(processor.response_audio)


async def test_validation_error_cleans_up_processor(
    hass: HomeAssistant,
    init_components: None,
    mock_chat_session: chat_session.ChatSession,
) -> None:
    """Test preflight validation cleans up without starting a run."""
    processor: _FailingValidationTestProcessor | None = None

    def create_processor(run) -> _FailingValidationTestProcessor:
        nonlocal processor
        processor = _FailingValidationTestProcessor(run)
        return processor

    with patch(
        "homeassistant.components.assist_pipeline.run._create_pipeline_processor",
        side_effect=create_processor,
    ):
        pipeline_input = assist_pipeline.pipeline.PipelineInput(
            run=assist_pipeline.pipeline.PipelineRun(
                hass,
                context=Context(),
                pipeline=assist_pipeline.pipeline.async_get_pipeline(hass),
                start_stage=assist_pipeline.PipelineStage.INTENT,
                end_stage=assist_pipeline.PipelineStage.INTENT,
                event_callback=lambda _event: None,
            ),
            session=mock_chat_session,
            intent_input="test",
        )
        with pytest.raises(PipelineRunValidationError, match="validation failed"):
            await pipeline_input.validate()

    assert processor is not None
    processor.cleanup.assert_called_once()
    assert not pipeline_input.run._registered
    with pytest.raises(PipelineAudioOutputError, match="validation failed"):
        await _collect(processor.response_audio)


async def test_pipeline_cancellation_fails_audio_output(
    hass: HomeAssistant,
    init_components: None,
    mock_chat_session: chat_session.ChatSession,
) -> None:
    """Test cancellation terminates a controller-owned output."""
    processor: _BlockingStreamingTestProcessor | None = None

    def create_processor(run) -> _BlockingStreamingTestProcessor:
        nonlocal processor
        processor = _BlockingStreamingTestProcessor(run)
        return processor

    with patch(
        "homeassistant.components.assist_pipeline.run._create_pipeline_processor",
        side_effect=create_processor,
    ):
        pipeline_input = assist_pipeline.pipeline.PipelineInput(
            run=assist_pipeline.pipeline.PipelineRun(
                hass,
                context=Context(),
                pipeline=assist_pipeline.pipeline.async_get_pipeline(hass),
                start_stage=assist_pipeline.PipelineStage.INTENT,
                end_stage=assist_pipeline.PipelineStage.INTENT,
                event_callback=lambda _event: None,
            ),
            session=mock_chat_session,
            intent_input="test",
        )
        pipeline_task = hass.async_create_task(
            pipeline_input.execute(validate=True),
        )
        assert processor is not None
        await processor.started.wait()
        consumer_task = hass.async_create_task(_collect(processor.response_audio))
        pipeline_task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await pipeline_task
        with pytest.raises(PipelineAudioOutputError):
            await consumer_task
