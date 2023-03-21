"""Voice Assistant Websocket API."""
import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import stt, websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .pipeline import (
    DEFAULT_TIMEOUT,
    AudioPipelineRequest,
    Pipeline,
    PipelineRun,
    TextPipelineRequest,
)

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "voice_assistant/run",
        vol.Optional("language"): str,
        vol.Optional("pipeline"): str,
        vol.Optional("intent_input"): str,
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
    if pipeline_id is not None:
        pipeline = hass.data[DOMAIN].get(pipeline_id)
        if pipeline is None:
            connection.send_error(
                msg["id"],
                "pipeline_not_found",
                f"Pipeline not found: {pipeline_id}",
            )
            return

    else:
        # Construct a pipeline for the required/configured language
        pipeline = Pipeline(
            name=language,
            language=language,
            stt_engine=None,  # cloud
            conversation_engine=None,  # default agent
            tts_engine=None,  # cloud
        )

    timeout = msg.get("timeout", DEFAULT_TIMEOUT)

    intent_input = msg.get("intent_input")
    if intent_input is None:
        _LOGGER.debug("Running audio pipeline")

        # Audio pipeline
        audio_queue: "asyncio.Queue[bytes]" = asyncio.Queue()

        async def stt_stream():
            while chunk := await audio_queue.get():
                _LOGGER.debug("Received %s byte(s) of audio", len(chunk))
                yield chunk

        def handle_binary(_hass, _connection, data: bytes):
            audio_queue.put_nowait(data)

        connection.async_register_binary_handler(handle_binary)

        run_task = hass.async_create_task(
            AudioPipelineRequest(
                stt_metadata=stt.SpeechMetadata(
                    language=language,
                    format=stt.AudioFormats.WAV,
                    codec=stt.AudioCodecs.PCM,
                    bit_rate=stt.AudioBitRates.BITRATE_16,
                    sample_rate=stt.AudioSampleRates.SAMPLERATE_16000,
                    channel=stt.AudioChannels.CHANNEL_MONO,
                ),
                stt_stream=stt_stream(),
                conversation_id=msg.get("conversation_id"),
            ).execute(
                PipelineRun(
                    hass,
                    connection.context(msg),
                    pipeline,
                    event_callback=lambda event: connection.send_event(
                        msg["id"], event.as_dict()
                    ),
                ),
                timeout=timeout,
            )
        )
    else:
        # Text pipeline
        run_task = hass.async_create_task(
            TextPipelineRequest(
                intent_input=msg["intent_input"],
                conversation_id=msg.get("conversation_id"),
            ).execute(
                PipelineRun(
                    hass,
                    connection.context(msg),
                    pipeline,
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

    # Task contains a timeout
    await run_task
