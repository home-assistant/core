"""Voice Assistant Websocket API."""
import asyncio
from collections.abc import Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import stt, websocket_api
from homeassistant.core import HomeAssistant, callback

from .pipeline import (
    DEFAULT_TIMEOUT,
    PipelineError,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    async_get_pipeline,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        # pylint: disable-next=unnecessary-lambda
        vol.Required("start_stage"): lambda val: PipelineStage(val),
        # pylint: disable-next=unnecessary-lambda
        vol.Required("end_stage"): lambda val: PipelineStage(val),
        vol.Optional("input"): {"text": str},
        vol.Optional("language"): str,
        vol.Optional("pipeline"): str,
        vol.Optional("conversation_id"): vol.Any(str, None),
        vol.Optional("timeout"): vol.Any(float, int),
    }
)
@websocket_api.async_response
async def websocket_run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a pipeline."""
    language = msg.get("language", hass.config.language)
    pipeline_id = msg.get("pipeline")
    pipeline = async_get_pipeline(
        hass,
        pipeline_id=pipeline_id,
        language=language,
    )
    if pipeline is None:
        connection.send_error(
            msg["id"],
            "pipeline-not-found",
            f"Pipeline not found: id={pipeline_id}, language={language}",
        )
        return

    timeout = msg.get("timeout", DEFAULT_TIMEOUT)
    start_stage = PipelineStage(msg["start_stage"])
    end_stage = PipelineStage(msg["end_stage"])
    handler_id: int | None = None
    unregister_handler: Callable[[], None] | None = None

    # Arguments to PipelineInput
    input_args: dict[str, Any] = {
        "conversation_id": msg.get("conversation_id"),
    }

    if start_stage == PipelineStage.STT:
        # Audio pipeline that will receive audio as binary websocket messages
        audio_queue: "asyncio.Queue[bytes]" = asyncio.Queue()

        async def stt_stream():
            # Yield until we receive an empty chunk
            while chunk := await audio_queue.get():
                yield chunk

        def handle_binary(_hass, _connection, data: bytes):
            # Forward to STT audio stream
            audio_queue.put_nowait(data)

        handler_id, unregister_handler = connection.async_register_binary_handler(
            handle_binary
        )

        # Audio input must be raw PCM at 16Khz with 16-bit mono samples
        input_args["stt_metadata"] = stt.SpeechMetadata(
            language=language,
            format=stt.AudioFormats.WAV,
            codec=stt.AudioCodecs.PCM,
            bit_rate=stt.AudioBitRates.BITRATE_16,
            sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
            channel=stt.AudioChannels.CHANNEL_MONO,
        )
        input_args["stt_stream"] = stt_stream()
    elif start_stage == PipelineStage.INTENT:
        # Input to conversation agent
        input_args["intent_input"] = msg["input"]["text"]
    elif start_stage == PipelineStage.TTS:
        # Input to text to speech system
        input_args["tts_input"] = msg["input"]["text"]

    run_task = hass.async_create_task(
        PipelineInput(**input_args).execute(
            PipelineRun(
                hass,
                context=connection.context(msg),
                pipeline=pipeline,
                start_stage=start_stage,
                end_stage=end_stage,
                event_callback=lambda event: connection.send_event(
                    msg["id"], event.as_dict()
                ),
            ),
            timeout=timeout,
        )
    )

    # Cancel pipeline if user unsubscribes
    connection.subscriptions[msg["id"]] = run_task.cancel

    # Confirm subscription
    connection.send_result(msg["id"])

    if handler_id is not None:
        # Send handler id to client
        connection.send_event(msg["id"], {"handler_id": handler_id})

    try:
        # Task contains a timeout
        await run_task
    except PipelineError as error:
        # Report more specific error when possible
        connection.send_error(msg["id"], error.code, error.message)
    finally:
        if unregister_handler is not None:
            # Unregister binary handler
            unregister_handler()
