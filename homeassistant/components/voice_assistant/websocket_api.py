"""Voice Assistant Websocket API."""
import asyncio
import logging
from collections.abc import Callable
from typing import Any

import voluptuous as vol

from homeassistant.components import stt, websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .pipeline import (
    async_get_pipeline,
    DEFAULT_TIMEOUT,
    PipelineInput,
    Pipeline,
    PipelineRun,
    PipelineError,
    PipelineStage,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Required("start_stage"): str,
        vol.Required("end_stage"): str,
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
    pipeline = async_get_pipeline(hass, pipeline_id=pipeline_id, language=language)
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
    unregister_handler: Callable[[], None] | None = None

    # Arguments to PipelineInput
    input_args: dict[str, Any] = {"conversation_id": msg.get("conversation_id")}

    if start_stage == PipelineStage.STT:
        # Audio pipeline
        audio_queue: "asyncio.Queue[bytes]" = asyncio.Queue()

        async def stt_stream():
            while chunk := await audio_queue.get():
                _LOGGER.debug("Received %s byte(s) of audio", len(chunk))
                yield chunk

        def handle_binary(_hass, _connection, data: bytes):
            audio_queue.put_nowait(data)

        handler_id, unregister_handler = connection.async_register_binary_handler(
            handle_binary
        )

        input_args["binary_handler_id"] = handler_id
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
        input_args["intent_input"] = msg["input"]["text"]
    elif start_stage == PipelineStage.TTS:
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

    connection.send_result(msg["id"])

    try:
        # Task contains a timeout
        await run_task
    except PipelineError as err:
        connection.send_error(msg["id"], err.code, err.message)
    finally:
        if unregister_handler is not None:
            # Unregister binary handler
            unregister_handler()
