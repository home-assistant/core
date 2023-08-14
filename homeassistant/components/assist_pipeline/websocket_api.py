"""Assist pipeline Websocket API."""
import asyncio

# Suppressing disable=deprecated-module is needed for Python 3.11
import audioop  # pylint: disable=deprecated-module
from collections.abc import AsyncGenerator, Callable
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import conversation, stt, tts, websocket_api
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.util import language as language_util

from .const import DOMAIN
from .error import PipelineNotFound
from .pipeline import (
    PipelineData,
    PipelineError,
    PipelineEvent,
    PipelineEventType,
    PipelineInput,
    PipelineRun,
    PipelineStage,
    WakeWordSettings,
    async_get_pipeline,
)

DEFAULT_TIMEOUT = 30
DEFAULT_WAKE_WORD_TIMEOUT = 3

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the websocket API."""
    websocket_api.async_register_command(hass, websocket_run)
    websocket_api.async_register_command(hass, websocket_list_languages)
    websocket_api.async_register_command(hass, websocket_list_runs)
    websocket_api.async_register_command(hass, websocket_get_run)


@websocket_api.websocket_command(
    vol.All(
        websocket_api.BASE_COMMAND_MESSAGE_SCHEMA.extend(
            {
                vol.Required("type"): "assist_pipeline/run",
                # pylint: disable-next=unnecessary-lambda
                vol.Required("start_stage"): lambda val: PipelineStage(val),
                # pylint: disable-next=unnecessary-lambda
                vol.Required("end_stage"): lambda val: PipelineStage(val),
                vol.Optional("input"): dict,
                vol.Optional("pipeline"): str,
                vol.Optional("conversation_id"): vol.Any(str, None),
                vol.Optional("device_id"): vol.Any(str, None),
                vol.Optional("timeout"): vol.Any(float, int),
            },
        ),
        cv.key_value_schemas(
            "start_stage",
            {
                PipelineStage.WAKE_WORD: vol.Schema(
                    {
                        vol.Required("input"): {
                            vol.Required("sample_rate"): int,
                            vol.Optional("timeout"): vol.Any(float, int),
                            vol.Optional("audio_seconds_to_buffer"): vol.Any(
                                float, int
                            ),
                        }
                    },
                    extra=vol.ALLOW_EXTRA,
                ),
                PipelineStage.STT: vol.Schema(
                    {vol.Required("input"): {vol.Required("sample_rate"): int}},
                    extra=vol.ALLOW_EXTRA,
                ),
                PipelineStage.INTENT: vol.Schema(
                    {vol.Required("input"): {"text": str}},
                    extra=vol.ALLOW_EXTRA,
                ),
                PipelineStage.TTS: vol.Schema(
                    {vol.Required("input"): {"text": str}},
                    extra=vol.ALLOW_EXTRA,
                ),
            },
        ),
    ),
)
@websocket_api.async_response
async def websocket_run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Run a pipeline."""
    pipeline_id = msg.get("pipeline")
    try:
        pipeline = async_get_pipeline(hass, pipeline_id=pipeline_id)
    except PipelineNotFound:
        connection.send_error(
            msg["id"],
            "pipeline-not-found",
            f"Pipeline not found: id={pipeline_id}",
        )
        return

    timeout = msg.get("timeout", DEFAULT_TIMEOUT)
    start_stage = PipelineStage(msg["start_stage"])
    end_stage = PipelineStage(msg["end_stage"])
    handler_id: int | None = None
    unregister_handler: Callable[[], None] | None = None
    wake_word_settings: WakeWordSettings | None = None

    # Arguments to PipelineInput
    input_args: dict[str, Any] = {
        "conversation_id": msg.get("conversation_id"),
        "device_id": msg.get("device_id"),
    }

    if start_stage in (PipelineStage.WAKE_WORD, PipelineStage.STT):
        # Audio pipeline that will receive audio as binary websocket messages
        audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        incoming_sample_rate = msg["input"]["sample_rate"]

        if start_stage == PipelineStage.WAKE_WORD:
            wake_word_settings = WakeWordSettings(
                timeout=msg["input"].get("timeout", DEFAULT_WAKE_WORD_TIMEOUT),
                audio_seconds_to_buffer=msg["input"].get("audio_seconds_to_buffer", 0),
            )

        async def stt_stream() -> AsyncGenerator[bytes, None]:
            state = None

            # Yield until we receive an empty chunk
            while chunk := await audio_queue.get():
                if incoming_sample_rate != 16000:
                    chunk, state = audioop.ratecv(
                        chunk, 2, 1, incoming_sample_rate, 16000, state
                    )
                yield chunk

        def handle_binary(
            _hass: HomeAssistant,
            _connection: websocket_api.ActiveConnection,
            data: bytes,
        ) -> None:
            # Forward to STT audio stream
            audio_queue.put_nowait(data)

        handler_id, unregister_handler = connection.async_register_binary_handler(
            handle_binary
        )

        # Audio input must be raw PCM at 16Khz with 16-bit mono samples
        input_args["stt_metadata"] = stt.SpeechMetadata(
            language=pipeline.stt_language or pipeline.language,
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
        # Input to text-to-speech system
        input_args["tts_input"] = msg["input"]["text"]

    input_args["run"] = PipelineRun(
        hass,
        context=connection.context(msg),
        pipeline=pipeline,
        start_stage=start_stage,
        end_stage=end_stage,
        event_callback=lambda event: connection.send_event(msg["id"], event),
        runner_data={
            "stt_binary_handler_id": handler_id,
            "timeout": timeout,
        },
        wake_word_settings=wake_word_settings,
    )

    pipeline_input = PipelineInput(**input_args)

    try:
        await pipeline_input.validate()
    except PipelineError as error:
        # Report more specific error when possible
        connection.send_error(msg["id"], error.code, error.message)
        return

    # Confirm subscription
    connection.send_result(msg["id"])

    run_task = hass.async_create_task(pipeline_input.execute())

    # Cancel pipeline if user unsubscribes
    connection.subscriptions[msg["id"]] = run_task.cancel

    try:
        # Task contains a timeout
        async with timeout(timeout):
            await run_task
    except asyncio.TimeoutError:
        pipeline_input.run.process_event(
            PipelineEvent(
                PipelineEventType.ERROR,
                {"code": "timeout", "message": "Timeout running pipeline"},
            )
        )
    finally:
        if unregister_handler is not None:
            # Unregister binary handler
            unregister_handler()


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_pipeline/pipeline_debug/list",
        vol.Required("pipeline_id"): str,
    }
)
def websocket_list_runs(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List pipeline runs for which debug data is available."""
    pipeline_data: PipelineData = hass.data[DOMAIN]
    pipeline_id = msg["pipeline_id"]

    if pipeline_id not in pipeline_data.pipeline_runs:
        connection.send_result(msg["id"], {"pipeline_runs": []})
        return

    pipeline_runs = pipeline_data.pipeline_runs[pipeline_id]

    connection.send_result(
        msg["id"],
        {
            "pipeline_runs": [
                {"pipeline_run_id": id, "timestamp": pipeline_run.timestamp}
                for id, pipeline_run in pipeline_runs.items()
            ]
        },
    )


@callback
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_pipeline/pipeline_debug/get",
        vol.Required("pipeline_id"): str,
        vol.Required("pipeline_run_id"): str,
    }
)
def websocket_get_run(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Get debug data for a pipeline run."""
    pipeline_data: PipelineData = hass.data[DOMAIN]
    pipeline_id = msg["pipeline_id"]
    pipeline_run_id = msg["pipeline_run_id"]

    if pipeline_id not in pipeline_data.pipeline_runs:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"pipeline_id {pipeline_id} not found",
        )
        return

    pipeline_runs = pipeline_data.pipeline_runs[pipeline_id]

    if pipeline_run_id not in pipeline_runs:
        connection.send_error(
            msg["id"],
            websocket_api.const.ERR_NOT_FOUND,
            f"pipeline_run_id {pipeline_run_id} not found",
        )
        return

    connection.send_result(
        msg["id"],
        {"events": pipeline_runs[pipeline_run_id].events},
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "assist_pipeline/language/list",
    }
)
@websocket_api.async_response
async def websocket_list_languages(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """List languages which are supported by a complete pipeline.

    This will return a list of languages which are supported by at least one stt, tts
    and conversation engine respectively.
    """
    conv_language_tags = await conversation.async_get_conversation_languages(hass)
    stt_language_tags = stt.async_get_speech_to_text_languages(hass)
    tts_language_tags = tts.async_get_text_to_speech_languages(hass)
    pipeline_languages: set[str] | None = None

    if conv_language_tags and conv_language_tags != MATCH_ALL:
        languages = set()
        for language_tag in conv_language_tags:
            dialect = language_util.Dialect.parse(language_tag)
            languages.add(dialect.language)
        pipeline_languages = languages

    if stt_language_tags:
        languages = set()
        for language_tag in stt_language_tags:
            dialect = language_util.Dialect.parse(language_tag)
            languages.add(dialect.language)
        if pipeline_languages is not None:
            pipeline_languages &= languages
        else:
            pipeline_languages = languages

    if tts_language_tags:
        languages = set()
        for language_tag in tts_language_tags:
            dialect = language_util.Dialect.parse(language_tag)
            languages.add(dialect.language)
        if pipeline_languages is not None:
            pipeline_languages &= languages
        else:
            pipeline_languages = languages

    connection.send_result(
        msg["id"],
        {"languages": pipeline_languages},
    )
